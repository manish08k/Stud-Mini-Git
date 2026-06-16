import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .vuln_scanner import ScanResult, VulnScanner
from .secret_scanner import SecretFinding, scan_directory


@dataclass
class AuditEvent:
    timestamp: float
    event_type: str
    actor: str
    resource: str
    action: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    success: bool = True


@dataclass
class AuditReport:
    generated_at: float
    project: str
    vuln_results: List[ScanResult] = field(default_factory=list)
    secret_findings: List[SecretFinding] = field(default_factory=list)
    events: List[AuditEvent] = field(default_factory=list)

    @property
    def has_critical(self) -> bool:
        return any(
            v.severity == "critical"
            for result in self.vuln_results
            for v in result.vulnerabilities
        )

    @property
    def total_vulnerabilities(self) -> int:
        return sum(len(r.vulnerabilities) for r in self.vuln_results)

    def summary(self) -> Dict[str, Any]:
        sev_counts: Dict[str, int] = {}
        for r in self.vuln_results:
            for v in r.vulnerabilities:
                sev_counts[v.severity] = sev_counts.get(v.severity, 0) + 1
        return {
            "total_vulnerabilities": self.total_vulnerabilities,
            "severities": sev_counts,
            "secret_findings": len(self.secret_findings),
            "has_critical": self.has_critical,
        }


class AuditLogger:
    def __init__(self, log_path: Path):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: AuditEvent) -> None:
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event)) + "\n")

    def read_events(self) -> List[AuditEvent]:
        if not self.log_path.exists():
            return []
        events = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(AuditEvent(**json.loads(line)))
        return events


class AuditService:
    def __init__(self, project_dir: Path, log_path: Optional[Path] = None,
                 vuln_scanner: Optional[VulnScanner] = None):
        self.project_dir = Path(project_dir)
        self.logger = AuditLogger(log_path or project_dir / ".stud" / "audit.log")
        self.vuln_scanner = vuln_scanner or VulnScanner()

    def run_full_audit(self, packages: Dict[str, str], project_name: str = "project") -> AuditReport:
        vuln_results = self.vuln_scanner.scan_all(packages)
        secret_findings = scan_directory(self.project_dir)
        events = self.logger.read_events()

        return AuditReport(
            generated_at=time.time(),
            project=project_name,
            vuln_results=vuln_results,
            secret_findings=secret_findings,
            events=events,
        )

    def record(self, event_type: str, actor: str, resource: str,
               action: str, success: bool = True, metadata: Optional[Dict] = None) -> None:
        event = AuditEvent(
            timestamp=time.time(),
            event_type=event_type,
            actor=actor,
            resource=resource,
            action=action,
            success=success,
            metadata=metadata or {},
        )
        self.logger.log(event)
