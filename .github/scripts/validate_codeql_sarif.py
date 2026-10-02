"""Fail closed when CodeQL SARIF contains HIGH/CRITICAL security findings."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

BLOCKING_SECURITY_SEVERITY = 7.0


def _sarif_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.is_dir():
        return []
    files = sorted(path.rglob("*.sarif"))
    files.extend(sorted(path.rglob("*.sarif.json")))
    seen: set[Path] = set()
    return [item for item in files if not (item in seen or seen.add(item))]


def _rule_for_result(run: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    driver = ((run.get("tool") or {}).get("driver") or {})
    rules = driver.get("rules") or []
    index = result.get("ruleIndex")
    if isinstance(index, int) and 0 <= index < len(rules):
        rule = rules[index]
        if isinstance(rule, dict):
            return rule

    rule_id = result.get("ruleId") or ((result.get("rule") or {}).get("id"))
    for rule in rules:
        if isinstance(rule, dict) and rule.get("id") == rule_id:
            return rule
    return {}


def _security_severity(rule: dict[str, Any], result: dict[str, Any]) -> float | None:
    candidates = [
        (result.get("properties") or {}).get("security-severity"),
        (rule.get("properties") or {}).get("security-severity"),
    ]
    for value in candidates:
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            raise ValueError(f"invalid CodeQL security-severity {value!r}") from None
    return None


def evaluate(paths: list[Path]) -> tuple[int, list[str]]:
    errors: list[str] = []
    blocking = 0
    sarif_count = 0
    result_count = 0

    for supplied in paths:
        files = _sarif_files(supplied)
        if not files:
            errors.append(f"no SARIF files found at {supplied}")
            continue
        for sarif in files:
            sarif_count += 1
            try:
                payload = json.loads(sarif.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"unable to read SARIF {sarif}: {exc}")
                continue

            runs = payload.get("runs")
            if not isinstance(runs, list) or not runs:
                errors.append(f"SARIF {sarif} contains no runs")
                continue

            for run in runs:
                if not isinstance(run, dict):
                    errors.append(f"SARIF {sarif} contains an invalid run")
                    continue
                for result in run.get("results") or []:
                    if not isinstance(result, dict):
                        errors.append(f"SARIF {sarif} contains an invalid result")
                        continue
                    result_count += 1
                    rule = _rule_for_result(run, result)
                    try:
                        severity = _security_severity(rule, result)
                    except ValueError as exc:
                        errors.append(f"{sarif}: {exc}")
                        continue
                    if severity is None:
                        tags = set((rule.get("properties") or {}).get("tags") or [])
                        if any("security" in str(tag).lower() for tag in tags):
                            errors.append(
                                f"{sarif}: security result {result.get('ruleId') or 'unknown'} "
                                "has no numeric security-severity"
                            )
                        continue
                    if severity >= BLOCKING_SECURITY_SEVERITY:
                        blocking += 1
                        message = ((result.get("message") or {}).get("text") or "").strip()
                        location = ""
                        locations = result.get("locations") or []
                        if locations:
                            physical = ((locations[0].get("physicalLocation") or {}))
                            artifact = ((physical.get("artifactLocation") or {}).get("uri") or "")
                            region = physical.get("region") or {}
                            line = region.get("startLine")
                            if artifact:
                                location = artifact + (f":{line}" if line else "")
                        print(
                            "BLOCKING CodeQL finding: "
                            f"rule={result.get('ruleId') or 'unknown'} "
                            f"security-severity={severity:g} "
                            f"location={location or 'unknown'} "
                            f"message={message or '<no message>'}"
                        )

    if sarif_count == 0 and not errors:
        errors.append("no CodeQL SARIF input was evaluated")

    print(
        f"CodeQL SARIF gate: files={sarif_count} results={result_count} "
        f"blocking={blocking} threshold={BLOCKING_SECURITY_SEVERITY:g}"
    )
    return blocking, errors


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: validate_codeql_sarif.py <sarif-file-or-directory> [...]", file=sys.stderr)
        return 2

    blocking, errors = evaluate([Path(item) for item in args])
    if errors:
        print("CodeQL SARIF gate failed closed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    if blocking:
        print(
            f"CodeQL SARIF gate rejected {blocking} HIGH/CRITICAL security finding(s)",
            file=sys.stderr,
        )
        return 1

    print("CodeQL SARIF gate passed: no HIGH/CRITICAL security findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
