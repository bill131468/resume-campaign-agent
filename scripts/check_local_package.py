from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import PurePosixPath


REQUIRED_SUFFIXES = {
    "README.md",
    "AI_HANDOFF.md",
    "pyproject.toml",
    "src/resume_campaign_agent/api.py",
    "browser_extension/manifest.json",
    "docs/LOCAL_USER_GUIDE.md",
    "scripts/setup_local.ps1",
    "scripts/start_local.ps1",
    "scripts/verify_local.ps1",
}
FORBIDDEN_PARTS = {
    ".git",
    ".project-to-act",
    ".venv",
    "deploy",
    "evidence",
    "release",
    "__pycache__",
}
FORBIDDEN_NAMES = {
    ".env.local",
    ".env.server",
    ".env.server.example",
    "DEPLOY_SERVER.md",
    "Dockerfile",
    "compose.yaml",
}
FORBIDDEN_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".log", ".sqlite", ".db"}
SECRET_PATTERNS = {
    "private key": re.compile(r"BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY"),
    "GitHub token": re.compile(r"gh[opurs]_[A-Za-z0-9]{20,}"),
    "OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "non-placeholder LLM key": re.compile(
        r"(?m)^LLM_API_KEY[ \t]*=[ \t]*(?!your-local-secret[ \t]*$)\S+"
    ),
    "temporary tunnel": re.compile(r"https://[^\s/]+\.trycloudflare\.com", re.I),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive")
    args = parser.parse_args()
    issues: list[str] = []

    with zipfile.ZipFile(args.archive) as package:
        names = [name.replace("\\", "/") for name in package.namelist() if not name.endswith("/")]
        paths = [PurePosixPath(name) for name in names]
        for required in REQUIRED_SUFFIXES:
            if not any(name.endswith("/" + required) for name in names):
                issues.append(f"missing required file: {required}")
        for name, path in zip(names, paths):
            lowered_parts = {part.lower() for part in path.parts}
            if lowered_parts & {part.lower() for part in FORBIDDEN_PARTS}:
                issues.append(f"forbidden directory in package: {name}")
                continue
            if path.name in FORBIDDEN_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES:
                issues.append(f"forbidden file in package: {name}")
                continue
            info = package.getinfo(name)
            if info.file_size > 2_000_000:
                continue
            try:
                content = package.read(name).decode("utf-8")
            except UnicodeDecodeError:
                continue
            for label, pattern in SECRET_PATTERNS.items():
                if pattern.search(content):
                    issues.append(f"{label} pattern in: {name}")

    if issues:
        print("LOCAL SOURCE PACKAGE CHECK FAILED")
        for issue in sorted(set(issues)):
            print(f"- {issue}")
        return 1
    print(f"LOCAL SOURCE PACKAGE CHECK PASSED ({len(names)} files checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
