from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from validate_security_evidence import validate_repository


def repository_report(*, secret_value: str | None = None) -> dict:
    result = {
        "Target": "docker/Dockerfile",
        "Class": "config",
        "Type": "dockerfile",
        "Misconfigurations": [],
        "Secrets": [],
    }
    if secret_value is not None:
        result["Secrets"] = [
            {
                "RuleID": "fixture-secret",
                "Category": "fixture",
                "Match": secret_value,
            }
        ]
    return {"Results": [result]}


class SecurityEvidenceSelfCheck(unittest.TestCase):
    def test_secret_material_never_appears_in_failure_diagnostics(self) -> None:
        canary = "credential-material-canary"
        output = io.StringIO()
        with redirect_stdout(output):
            with self.assertRaises(ValueError) as raised:
                validate_repository(repository_report(secret_value=canary))

        self.assertEqual(
            str(raised.exception),
            "repository Trivy gate contains gated findings after a successful scan",
        )
        self.assertNotIn(canary, str(raised.exception))
        self.assertNotIn(canary, output.getvalue())

    def test_success_log_uses_constant_secret_status(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            validate_repository(repository_report())

        rendered = output.getvalue()
        self.assertIn("secretFindings=none", rendered)
        self.assertNotIn("secrets=", rendered)


if __name__ == "__main__":
    unittest.main(verbosity=2)
