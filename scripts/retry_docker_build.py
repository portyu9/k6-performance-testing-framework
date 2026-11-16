#!/usr/bin/env python3
"""Bounded, fail-closed retry for *verified* transient Go proxy failures during k6 image builds."""
from __future__ import annotations

from collections import deque
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
ATTEMPTS = 2
RETRY_SECONDS = 5
IMAGE = re.compile(r"qa-k6:[a-z][a-z0-9_-]{1,31}\Z")
GO_PROXY_HTTP2 = re.compile(
    r'read "https://proxy\.golang\.org/[^"\r\n]+": stream error: '
    r'stream ID [0-9]+; INTERNAL_ERROR; received from peer'
)
GO_PROXY_TIMEOUT = re.compile(
    r'Get "https://proxy\.golang\.org/[^"\r\n]+": '
    r'(?:net/http: TLS handshake timeout|context deadline exceeded|'
    r'dial tcp [^\r\n]+: i/o timeout)'
)
DETERMINISTIC_BLOCKER = re.compile(
    r"checksum mismatch|verification failed|x509:|certificate verify|"
    r"unauthorized|permission denied|forbidden|"
    r"module lookup disabled|does not contain package",
    re.IGNORECASE,
)


def is_retryable_proxy_failure(log: str) -> bool:
    """Never retry a policy, checksum, certificate, or ambiguous build failure."""
    return bool(
        not DETERMINISTIC_BLOCKER.search(log)
        and (GO_PROXY_HTTP2.search(log) or GO_PROXY_TIMEOUT.search(log))
    )


def run_docker_build(argv: list[str]) -> tuple[int, str]:
    """Stream all build logs, retaining only a bounded tail for classification."""
    tail: deque[str] = deque(maxlen=5000)
    with subprocess.Popen(
        argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, errors="replace", bufsize=1,
    ) as process:
        if process.stdout is None:
            raise RuntimeError("Docker log stream was not opened")
        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            tail.append(line)
        code = process.wait()
    return code, "".join(tail)


def build_image(
    tag: str,
    *,
    runner: Callable[[list[str]], tuple[int, str]] = run_docker_build,
    sleeper: Callable[[float], None] = time.sleep,
) -> int:
    if IMAGE.fullmatch(tag) is None:
        raise ValueError("image tag must be a single canonical qa-k6 image reference")
    command = ["docker", "build", "-f", "docker/Dockerfile", "-t", tag, "."]
    for attempt in range(1, ATTEMPTS + 1):
        exit_code, evidence = runner(command)
        if exit_code == 0:
            return 0
        if attempt == ATTEMPTS or not is_retryable_proxy_failure(evidence):
            print(
                f"k6 image build failed on attempt {attempt}/{ATTEMPTS}; "
                "no further retry is eligible",
                file=sys.stderr,
            )
            return exit_code or 1
        print(
            f"k6 image build attempt {attempt}/{ATTEMPTS}: exact Go module "
            f"proxy transport failure verified; retrying once after {RETRY_SECONDS}s",
            file=sys.stderr,
        )
        sleeper(RETRY_SECONDS)
    raise AssertionError("unreachable bounded retry state")


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: retry_docker_build.py qa-k6:<tag>", file=sys.stderr)
        return 2
    try:
        return build_image(argv[0])
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"k6 image build invocation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
