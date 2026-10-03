"""Fail closed when first-party code exists without a security scanner."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SECURITY_WORKFLOW = ROOT / ".github" / "workflows" / "security.yml"

CODEQL_BY_SUFFIX = {
    ".js": "javascript-typescript",
    ".jsx": "javascript-typescript",
    ".ts": "javascript-typescript",
    ".tsx": "javascript-typescript",
    ".py": "python",
    ".pyi": "python",
    ".go": "go",
}
SHELL_SUFFIXES = {".sh", ".bash", ".zsh", ".ksh"}
KNOWN_CODE_SUFFIXES = set(CODEQL_BY_SUFFIX) | SHELL_SUFFIXES | {
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp",
    ".cs", ".java", ".kt", ".kts", ".rb", ".rs", ".swift",
    ".php", ".scala", ".lua", ".ps1",
}
SHELL_SHEBANG = re.compile(r"^#!.*\b(?:ba|da|k|z)?sh\b")


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [
        ROOT / item.decode("utf-8")
        for item in result.stdout.split(b"\0")
        if item
    ]


def main() -> int:
    errors: list[str] = []
    files = tracked_files()
    workflow_text = SECURITY_WORKFLOW.read_text(encoding="utf-8")

    discovered_codeql: set[str] = set()
    shell_files: list[Path] = []

    for path in files:
        suffix = path.suffix.lower()
        relative = path.relative_to(ROOT)

        if suffix in CODEQL_BY_SUFFIX:
            discovered_codeql.add(CODEQL_BY_SUFFIX[suffix])
        elif suffix in SHELL_SUFFIXES:
            shell_files.append(path)
        elif suffix in KNOWN_CODE_SUFFIXES:
            errors.append(
                f"tracked source {relative} has no scanner mapping; extend the security gate before merging"
            )

        if path.is_file():
            try:
                first_line = path.open("r", encoding="utf-8").readline().rstrip("\n")
            except UnicodeDecodeError:
                first_line = ""
            if SHELL_SHEBANG.search(first_line) and suffix not in SHELL_SUFFIXES:
                errors.append(
                    f"tracked shell entrypoint {relative} lacks a shell-scanned suffix"
                )

    expected_codeql = {"javascript-typescript", "python", "go"}
    if discovered_codeql != expected_codeql:
        errors.append(
            "first-party CodeQL language inventory mismatch: "
            f"found {sorted(discovered_codeql)}, expected {sorted(expected_codeql)}"
        )
    if not shell_files:
        errors.append("no tracked shell files found for ShellCheck coverage")

    workflows = sorted((ROOT / ".github" / "workflows").glob("*.y*ml"))
    if not workflows:
        errors.append("no GitHub Actions workflows found for CodeQL Actions analysis")

    required_contracts = {
        "CodeQL JavaScript/Python/Actions": "languages: javascript-typescript,python,actions",
        "CodeQL Go": "languages: go",
        "CodeQL Go manual build": "build-mode: manual",
        "CodeQL Go pinned-module build": "go test -mod=mod ./...",
        "ShellCheck tracked shell discovery": "git ls-files -z '*.sh' '*.bash' '*.zsh' '*.ksh'",
        "ShellCheck pinned release": "shellcheck-v0.11.0.linux.x86_64.tar.xz",
        "ShellCheck pinned digest": "8c3be12b05d5c177a04c29e3c78ce89ac86f1595681cab149b65b97c4e227198",
        "repository misconfiguration/secret scan": "scanners: misconfig,secret",
        "built-image vulnerability scan": "scanners: vuln",
        "full security aggregate": (
            "needs: [supply-chain-policy, codeql_source, codeql_go, shellcheck, "
            "trivy-repository, container-image, dependency-review]"
        ),
    }
    for name, needle in required_contracts.items():
        if needle not in workflow_text:
            errors.append(f"security workflow is missing {name}")

    if workflow_text.count("python3 .github/scripts/validate_codeql_sarif.py") != 2:
        errors.append("security workflow must enforce zero CodeQL alerts for source and Go scans")
    if workflow_text.count("Upload CodeQL source SARIF evidence") != 1:
        errors.append("security workflow must retain source-stack CodeQL SARIF evidence")
    if workflow_text.count("Upload CodeQL Go SARIF evidence") != 1:
        errors.append("security workflow must retain Go CodeQL SARIF evidence")
    sarif_gate = (ROOT / ".github" / "scripts" / "validate_codeql_sarif.py").read_text(encoding="utf-8")
    if "CodeQL zero-alert gate rejected" not in sarif_gate:
        errors.append("CodeQL SARIF gate must reject every code-scanning result")

    if errors:
        print("Security stack coverage contract failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Security stack coverage contract: JS/TS, Python, Go, Actions, shell, repository config/secrets, and built image are gated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
