#!/usr/bin/env python3
"""Negative and positive fixtures for fail-closed k6 Docker build retry."""
from __future__ import annotations

import unittest

from retry_docker_build import build_image, is_retryable_proxy_failure

TRANSIENT = (
    '#14 65.81 github.com/dlclark/regexp2/v2@v2.7.2: '
    'read "https://proxy.golang.org/github.com/dlclark/regexp2/v2/@v/v2.7.2.zip": '
    'stream error: stream ID 125; INTERNAL_ERROR; received from peer\n'
    '#14 ERROR: process did not complete successfully: exit code: 1'
)


class RetryDockerBuildContract(unittest.TestCase):
    def test_exact_upstream_http2_error_retries_once_and_keeps_command_immutable(self) -> None:
        calls: list[list[str]] = []
        sleeps: list[float] = []
        results = iter([(1, TRANSIENT), (0, "built")])

        def run(command: list[str]) -> tuple[int, str]:
            calls.append(command[:])
            return next(results)

        self.assertEqual(build_image("qa-k6:smoke", runner=run, sleeper=sleeps.append), 0)
        self.assertEqual(calls, [["docker", "build", "-f", "docker/Dockerfile",
                                  "-t", "qa-k6:smoke", "."]] * 2)
        self.assertEqual(sleeps, [5])

    def test_repeated_transient_is_capped_and_fails_closed(self) -> None:
        calls: list[list[str]] = []
        results = iter([(2, TRANSIENT), (3, TRANSIENT)])
        def run(command: list[str]) -> tuple[int, str]:
            calls.append(command)
            return next(results)
        self.assertEqual(build_image("qa-k6:ci", runner=run, sleeper=lambda _: None), 3)
        self.assertEqual(len(calls), 2)

    def test_deterministic_or_ambiguous_failure_is_never_retried(self) -> None:
        failures = [
            "Dockerfile:28: go: compilation failed",
            TRANSIENT + "\ngo: checksum mismatch",
            TRANSIENT + "\nerror: permission denied",
            TRANSIENT + "\nx509: certificate signed by unknown authority",
            'read "https://attacker.invalid/evil.zip": stream error: '
            'stream ID 1; INTERNAL_ERROR; received from peer',
            'read "http://proxy.golang.org/evil.zip": stream error: '
            'stream ID 1; INTERNAL_ERROR; received from peer',
        ]
        for failure in failures:
            with self.subTest(failure=failure[:50]):
                self.assertFalse(is_retryable_proxy_failure(failure))
                calls: list[list[str]] = []
                def fail(command: list[str]) -> tuple[int, str]:
                    calls.append(command)
                    return 1, failure
                self.assertEqual(build_image("qa-k6:security", runner=fail,
                                             sleeper=lambda _: None), 1)
                self.assertEqual(len(calls), 1)

    def test_does_not_retry_on_success(self) -> None:
        calls: list[list[str]] = []
        def successful(command: list[str]) -> tuple[int, str]:
            calls.append(command)
            return 0, "built"
        self.assertEqual(build_image("qa-k6:extended", runner=successful,
                                     sleeper=lambda _: None), 0)
        self.assertEqual(len(calls), 1)

    def test_rejects_injection_in_image_tag(self) -> None:
        for tag in ("qa-k6:foo;curl evil", "--privileged", "other:ci", "qa-k6:"):
            with self.subTest(tag=tag):
                with self.assertRaises(ValueError):
                    build_image(tag, runner=lambda _: (0, ""), sleeper=lambda _: None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
