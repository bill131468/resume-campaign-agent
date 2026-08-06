from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = {
    "README.md",
    "LICENSE",
    "NOTICE",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "CHANGELOG.md",
    "docs/QUICKSTART.md",
    "docs/LOCAL_USER_GUIDE.md",
    "docs/AI_HANDOFF_LOCAL.md",
    "docs/ARCHITECTURE.md",
    "docs/API.md",
    "docs/TESTING.md",
    "docs/SECURITY.md",
    "docs/TROUBLESHOOTING.md",
    "docs/examples/github-actions-ci.yml",
}
FORBIDDEN_TRACKED_PARTS = {
    ".env.local",
    ".env.server",
    ".project-to-act",
    "artifacts",
    "release",
    "__pycache__",
}
FORBIDDEN_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".log"}
SECRET_PATTERNS = {
    "private key": re.compile(r"BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY"),
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "GitHub token": re.compile(r"gh[opurs]_[A-Za-z0-9]{20,}"),
    "OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "non-empty LLM key": re.compile(
        r"(?m)^LLM_API_KEY[ \t]*=[ \t]*(?!your-local-secret[ \t]*$)\S+"
    ),
    "Windows user path": re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+", re.IGNORECASE),
}
SAFE_IPV4 = {"0.0.0.0", "127.0.0.1", "127.0.0.0"}
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return [
            path.relative_to(ROOT).as_posix()
            for path in ROOT.rglob("*")
            if path.is_file() and ".git" not in path.parts
        ]
    return [line for line in result.stdout.splitlines() if line]


def main() -> int:
    issues: list[str] = []
    missing = sorted(path for path in REQUIRED_FILES if not (ROOT / path).is_file())
    issues.extend(f"missing required file: {path}" for path in missing)

    for relative in tracked_files():
        path = Path(relative)
        lowered_parts = {part.lower() for part in path.parts}
        if lowered_parts & FORBIDDEN_TRACKED_PARTS or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            issues.append(f"forbidden tracked path: {relative}")
            continue
        absolute = ROOT / path
        try:
            if absolute.stat().st_size > 2_000_000:
                continue
            content = absolute.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                issues.append(f"{label} pattern in: {relative}")
        for address in IPV4.findall(content):
            octets = address.split(".")
            if all(int(value) <= 255 for value in octets) and address not in SAFE_IPV4:
                issues.append(f"non-example public IPv4 address in: {relative}")
                break

    if issues:
        print("PUBLIC RELEASE CHECK FAILED")
        for issue in sorted(set(issues)):
            print(f"- {issue}")
        return 1
    print(f"PUBLIC RELEASE CHECK PASSED ({len(tracked_files())} files checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
