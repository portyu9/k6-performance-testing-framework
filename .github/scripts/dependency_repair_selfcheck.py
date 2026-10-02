#!/usr/bin/env python3
from __future__ import annotations

import unittest

from dependency_governance_lib.models import GovernanceError
from dependency_governance_lib.provenance import REPAIR_MESSAGE
from dependency_repair import _verify_repair_publisher, synchronize_dockerfile

OLD_COMMIT = "1" * 40
NEW_COMMIT = "2" * 40
SOURCE = f"""ARG K6_VERSION=2.2.0
ARG K6_COMMIT={OLD_COMMIT}

FROM grafana/k6:2.3.0@sha256:{'a' * 64} AS upstream-release
"""

class PublisherApi:
    def __init__(self, login: str = "portyu9", user_id: int = 35150859):
        self.identity = {"login": login, "id": user_id}

    def get(self, path: str):
        if path == "https://api.github.com/user":
            return self.identity
        raise AssertionError(path)



class DependencyRepairSelfCheck(unittest.TestCase):
    def test_repair_commit_allows_dependabot_native_rebase(self) -> None:
        self.assertIn("[dependabot skip]", REPAIR_MESSAGE)


    def test_repair_publisher_requires_configured_owner_identity(self) -> None:
        config = {"ownerApprovalLogin": "portyu9", "ownerApprovalUserId": 35150859}
        good = PublisherApi()
        self.assertIs(_verify_repair_publisher(good, config), good)
        for publisher in (None, PublisherApi("github-actions[bot]", 41898282)):
            with self.assertRaises(GovernanceError):
                _verify_repair_publisher(publisher, config)

    def test_source_provenance_is_updated_exactly(self) -> None:
        repaired = synchronize_dockerfile(
            SOURCE,
            old_version="2.2.0",
            new_version="2.3.0",
            new_commit=NEW_COMMIT,
        )
        self.assertIn("ARG K6_VERSION=2.3.0", repaired)
        self.assertIn(f"ARG K6_COMMIT={NEW_COMMIT}", repaired)
        self.assertIn("FROM grafana/k6:2.3.0@", repaired)
        self.assertEqual(
            [line for line in repaired.splitlines() if line != ""],
            [
                "ARG K6_VERSION=2.3.0",
                f"ARG K6_COMMIT={NEW_COMMIT}",
                f"FROM grafana/k6:2.3.0@sha256:{'a' * 64} AS upstream-release",
            ],
        )

    def test_source_version_mismatch_fails_closed(self) -> None:
        with self.assertRaises(GovernanceError):
            synchronize_dockerfile(
                SOURCE,
                old_version="2.1.0",
                new_version="2.3.0",
                new_commit=NEW_COMMIT,
            )

    def test_noncanonical_commit_fails_closed(self) -> None:
        with self.assertRaises(GovernanceError):
            synchronize_dockerfile(
                SOURCE,
                old_version="2.2.0",
                new_version="2.3.0",
                new_commit="not-a-sha",
            )

    def test_duplicate_source_pins_fail_closed(self) -> None:
        with self.assertRaises(GovernanceError):
            synchronize_dockerfile(
                SOURCE + "\nARG K6_VERSION=2.2.0\n",
                old_version="2.2.0",
                new_version="2.3.0",
                new_commit=NEW_COMMIT,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
