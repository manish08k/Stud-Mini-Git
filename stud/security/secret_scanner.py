import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PATTERNS: Dict[str, str] = {
    "aws_access_key":      r"(?<![A-Z0-9])(AKIA[0-9A-Z]{16})(?![A-Z0-9])",
    "aws_secret_key":      r"(?i)aws.{0,20}secret.{0,20}['\"]([A-Za-z0-9/+=]{40})['\"]",
    "github_token":        r"ghp_[A-Za-z0-9]{36}",
    "github_oauth":        r"gho_[A-Za-z0-9]{36}",
    "github_app_token":    r"(ghu|ghs)_[A-Za-z0-9]{36}",
    "stripe_key":          r"sk_(live|test)_[A-Za-z0-9]{24,}",
    "sendgrid_api_key":    r"SG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}",
    "jwt":                 r"eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+",
    "private_key_header":  r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "generic_secret":      r"(?i)(secret|password|passwd|pwd|api[_-]?key|token)\s*[:=]\s*['\"]([^'\"]{8,})['\"]",
    "generic_bearer":      r"(?i)bearer\s+([A-Za-z0-9\-._~+/]{20,})",
}

ENTROPY_THRESHOLD = 4.5
ENTROPY_MIN_LENGTH = 20

SKIP_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2",
                   ".ttf", ".eot", ".svg", ".pdf", ".zip", ".tar", ".gz", ".lock"}

SKIP_DIRS = {".git", ".stud", "node_modules", "__pycache__", "stud_modules", ".venv", "dist", "build"}


@dataclass
class SecretFinding:
    file: str
    line: int
    col: int
    rule: str
    matched: str
    entropy: Optional[float] = None


def _shannon_entropy(text: str) -> float:
    if not text:
        return 0.0
    freq: Dict[str, int] = {}
    for ch in text:
        freq[ch] = freq.get(ch, 0) + 1
    n = len(text)
    return -sum((c / n) * math.log2(c / n) for c in freq.values())


def scan_text(text: str, filename: str = "<text>") -> List[SecretFinding]:
    findings: List[SecretFinding] = []
    lines = text.splitlines()

    for lineno, line in enumerate(lines, start=1):
        for rule, pattern in PATTERNS.items():
            for m in re.finditer(pattern, line):
                matched = m.group(0)
                findings.append(SecretFinding(
                    file=filename, line=lineno,
                    col=m.start() + 1, rule=rule,
                    matched=matched[:80],
                ))

        tokens = re.findall(r"[A-Za-z0-9+/=_\-]{%d,}" % ENTROPY_MIN_LENGTH, line)
        for token in tokens:
            ent = _shannon_entropy(token)
            if ent >= ENTROPY_THRESHOLD:
                findings.append(SecretFinding(
                    file=filename, line=lineno,
                    col=line.find(token) + 1,
                    rule="high_entropy_string",
                    matched=token[:80],
                    entropy=round(ent, 3),
                ))

    return findings


def scan_file(path: Path) -> List[SecretFinding]:
    path = Path(path)
    if path.suffix.lower() in SKIP_EXTENSIONS:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, PermissionError):
        return []
    return scan_text(text, filename=str(path))


def scan_directory(root: Path) -> List[SecretFinding]:
    root = Path(root)
    findings: List[SecretFinding] = []
    for item in root.rglob("*"):
        if any(part in SKIP_DIRS for part in item.parts):
            continue
        if item.is_file():
            findings.extend(scan_file(item))
    return findings
