import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Vulnerability:
    cve_id: str
    package: str
    affected_versions: str
    severity: str
    description: str
    fix_version: Optional[str] = None


@dataclass
class ScanResult:
    package: str
    version: str
    vulnerabilities: List[Vulnerability] = field(default_factory=list)

    @property
    def safe(self) -> bool:
        return len(self.vulnerabilities) == 0


class VulnScanner:
    """
    Vulnerability scanner that checks dependencies against OSV (osv.dev) API.
    https://google.github.io/osv.dev/post-v1-query/
    """

    OSV_API = "https://api.osv.dev/v1/query"

    def __init__(self, timeout: float = 30.0, offline_db: Optional[Dict] = None):
        self.timeout = timeout
        self.offline_db: Dict[str, List[dict]] = offline_db or {}

    def _osv_query(self, package: str, version: str) -> List[dict]:
        payload = json.dumps({
            "version": version,
            "package": {"name": package, "ecosystem": "PyPI"},
        }).encode("utf-8")
        req = urllib.request.Request(
            self.OSV_API, data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("vulns", [])
        except urllib.error.URLError:
            return []

    def _offline_query(self, package: str, version: str) -> List[Vulnerability]:
        vulns = self.offline_db.get(package, [])
        results = []
        for v in vulns:
            results.append(Vulnerability(
                cve_id=v.get("id", ""),
                package=package,
                affected_versions=v.get("affected", ""),
                severity=v.get("severity", "unknown"),
                description=v.get("summary", ""),
                fix_version=v.get("fix"),
            ))
        return results

    def scan_package(self, package: str, version: str) -> ScanResult:
        if self.offline_db:
            vulns = self._offline_query(package, version)
            return ScanResult(package=package, version=version, vulnerabilities=vulns)

        raw_vulns = self._osv_query(package, version)
        vulns = []
        for v in raw_vulns:
            aliases = v.get("aliases", [])
            cve = next((a for a in aliases if a.startswith("CVE-")), v.get("id", ""))
            affected_str = ", ".join(
                r.get("versions", ["unknown"])[0]
                for r in v.get("affected", [])[:1]
            )
            severity = "unknown"
            for sev in v.get("severity", []):
                if sev.get("type") == "CVSS_V3":
                    score = float(sev.get("score", "0").split("/")[0] if "/" not in sev.get("score", "") else "0")
                    if score >= 9:
                        severity = "critical"
                    elif score >= 7:
                        severity = "high"
                    elif score >= 4:
                        severity = "medium"
                    else:
                        severity = "low"
                    break

            fix_version = None
            for affected in v.get("affected", []):
                for rng in affected.get("ranges", []):
                    for evt in rng.get("events", []):
                        if "fixed" in evt:
                            fix_version = evt["fixed"]

            vulns.append(Vulnerability(
                cve_id=cve,
                package=package,
                affected_versions=affected_str,
                severity=severity,
                description=v.get("summary", ""),
                fix_version=fix_version,
            ))

        return ScanResult(package=package, version=version, vulnerabilities=vulns)

    def scan_all(self, packages: Dict[str, str]) -> List[ScanResult]:
        return [self.scan_package(name, version) for name, version in packages.items()]
