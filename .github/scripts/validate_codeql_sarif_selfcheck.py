from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from validate_codeql_sarif import BLOCKING_SECURITY_SEVERITY, evaluate


def sarif(*, security_severity: str | None, security_tag: bool = True) -> dict:
    properties: dict[str, object] = {}
    if security_severity is not None:
        properties["security-severity"] = security_severity
    if security_tag:
        properties["tags"] = ["security", "external/cwe/cwe-079"]
    return {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "CodeQL",
                        "rules": [
                            {
                                "id": "js/example",
                                "properties": properties,
                            }
                        ],
                    }
                },
                "results": [
                    {
                        "ruleId": "js/example",
                        "ruleIndex": 0,
                        "message": {"text": "fixture"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "lib/client.js"},
                                    "region": {"startLine": 1},
                                }
                            }
                        ],
                    }
                ],
            }
        ],
    }


class CodeqlSarifGateSelfCheck(unittest.TestCase):
    def evaluate_fixture(self, payload: dict) -> tuple[int, list[str]]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.sarif"
            path.write_text(json.dumps(payload), encoding="utf-8")
            return evaluate([path])

    def test_threshold_is_high_severity(self) -> None:
        self.assertEqual(BLOCKING_SECURITY_SEVERITY, 7.0)

    def test_medium_security_finding_is_reported_but_not_blocking(self) -> None:
        blocking, errors = self.evaluate_fixture(sarif(security_severity="6.9"))
        self.assertEqual(blocking, 0)
        self.assertEqual(errors, [])

    def test_high_security_finding_blocks(self) -> None:
        blocking, errors = self.evaluate_fixture(sarif(security_severity="7.0"))
        self.assertEqual(blocking, 1)
        self.assertEqual(errors, [])

    def test_security_result_without_numeric_severity_fails_closed(self) -> None:
        blocking, errors = self.evaluate_fixture(sarif(security_severity=None))
        self.assertEqual(blocking, 0)
        self.assertTrue(any("no numeric security-severity" in item for item in errors))

    def test_missing_sarif_fails_closed(self) -> None:
        blocking, errors = evaluate([Path("/definitely/missing/codeql-results")])
        self.assertEqual(blocking, 0)
        self.assertTrue(any("no SARIF files found" in item for item in errors))

    def test_nonsecurity_result_without_security_severity_is_not_promoted(self) -> None:
        blocking, errors = self.evaluate_fixture(
            sarif(security_severity=None, security_tag=False)
        )
        self.assertEqual(blocking, 0)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
