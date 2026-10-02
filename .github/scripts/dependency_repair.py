#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import re
import urllib.parse
from pathlib import Path
from typing import Any

from dependency_governance_lib.github import GitHubApi, classify_ecosystem, parse_dependabot_metadata
from dependency_governance_lib.models import GovernanceError, load_config, parse_positive_integer
from dependency_governance_lib.provenance import validate_provenance
from dependency_governance_lib.semantics import validate_docker

TRUSTED_BASE_BRANCH = "main"
REPAIR_MESSAGE = "chore: synchronize k6 source provenance"
DEPENDABOT_DOCKER_BRANCH = re.compile(r"^dependabot/docker/[A-Za-z0-9._/-]+$")
K6_VERSION_LINE = re.compile(r"(?m)^ARG K6_VERSION=([0-9]+\.[0-9]+\.[0-9]+)$")
K6_COMMIT_LINE = re.compile(r"(?m)^ARG K6_COMMIT=([0-9a-f]{40})$")


def synchronize_dockerfile(
    text: str, *, old_version: str, new_version: str, new_commit: str
) -> str:
    version_matches = K6_VERSION_LINE.findall(text)
    commit_matches = K6_COMMIT_LINE.findall(text)
    if len(version_matches) != 1 or len(commit_matches) != 1:
        raise GovernanceError("Dockerfile must contain exactly one K6_VERSION and K6_COMMIT source pin")
    if version_matches[0] != old_version:
        raise GovernanceError(
            f"Dockerfile source version {version_matches[0]} does not match Dependabot marker base {old_version}"
        )
    if not re.fullmatch(r"[0-9a-f]{40}", new_commit):
        raise GovernanceError("resolved k6 release commit is not a canonical 40-character SHA")
    updated = K6_VERSION_LINE.sub(f"ARG K6_VERSION={new_version}", text, count=1)
    updated = K6_COMMIT_LINE.sub(f"ARG K6_COMMIT={new_commit}", updated, count=1)
    if updated == text:
        raise GovernanceError("k6 source provenance repair produced no change")
    return updated


def _current_main_sha(api: GitHubApi, config: dict[str, Any]) -> str:
    branch = api.get(f"/branches/{urllib.parse.quote(config['baseBranch'], safe='')}")
    sha = str((branch.get("commit") or {}).get("sha") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise GovernanceError("unable to resolve current main SHA")
    return sha


def _resolve_k6_release_commit(api: GitHubApi, version: str) -> str:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise GovernanceError(f"unsafe k6 release version {version!r}")
    ref = api.get(
        "https://api.github.com/repos/grafana/k6/git/ref/tags/"
        + urllib.parse.quote(f"v{version}", safe="")
    )
    obj = (ref or {}).get("object") or {}
    for _ in range(4):
        kind = obj.get("type")
        sha = str(obj.get("sha") or "")
        if kind == "commit" and re.fullmatch(r"[0-9a-f]{40}", sha):
            return sha
        if kind != "tag" or not re.fullmatch(r"[0-9a-f]{40}", sha):
            break
        tag = api.get(f"https://api.github.com/repos/grafana/k6/git/tags/{sha}")
        obj = (tag or {}).get("object") or {}
    raise GovernanceError(f"unable to resolve v{version} to an exact grafana/k6 commit")


def _create_blob(api: GitHubApi, text: str) -> str:
    result = api.post(
        "/git/blobs",
        {"content": base64.b64encode(text.encode("utf-8")).decode("ascii"), "encoding": "base64"},
    )
    sha = str((result or {}).get("sha") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise GovernanceError("GitHub did not return a valid repair blob SHA")
    return sha


def _publish_repair(
    api: GitHubApi,
    *,
    branch: str,
    source_head: str,
    dockerfile: str,
) -> str:
    if not DEPENDABOT_DOCKER_BRANCH.fullmatch(branch):
        raise GovernanceError("repair accepts Dependabot Docker branches only")
    git_commit = api.get(f"/git/commits/{source_head}")
    base_tree = str(((git_commit or {}).get("tree") or {}).get("sha") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", base_tree):
        raise GovernanceError("unable to resolve Dependabot source tree")

    tree = api.post(
        "/git/trees",
        {
            "base_tree": base_tree,
            "tree": [
                {
                    "path": "docker/Dockerfile",
                    "mode": "100644",
                    "type": "blob",
                    "sha": _create_blob(api, dockerfile),
                }
            ],
        },
    )
    tree_sha = str((tree or {}).get("sha") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", tree_sha):
        raise GovernanceError("GitHub did not return a valid repair tree SHA")

    message = (
        f"{REPAIR_MESSAGE}\n\n"
        f"Generated from Dependabot source head {source_head} by trusted default-branch "
        "dependency-repair."
    )
    commit = api.post(
        "/git/commits",
        {"message": message, "tree": tree_sha, "parents": [source_head]},
    )
    repair_sha = str((commit or {}).get("sha") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", repair_sha):
        raise GovernanceError("GitHub did not return a valid repair commit SHA")

    ref_path = "/git/refs/heads/" + urllib.parse.quote(branch, safe="/")
    current = api.get(ref_path)
    if str(((current or {}).get("object") or {}).get("sha") or "") != source_head:
        raise GovernanceError("Dependabot branch moved before atomic source-provenance publication")
    api.patch(ref_path, {"sha": repair_sha, "force": False})
    return repair_sha


def repair_pull(
    api: GitHubApi,
    number: int,
    config: dict[str, Any],
) -> dict[str, Any]:
    safe_number = parse_positive_integer(number, "pull request number")
    pull = api.get(f"/pulls/{safe_number}")
    user = pull.get("user") or {}
    if user.get("login") != config["botLogin"] or user.get("id") != config["botUserId"]:
        return {"pr": safe_number, "skipped": True, "reason": "not canonical Dependabot"}
    if pull.get("state") != "open":
        return {"pr": safe_number, "skipped": True, "reason": "pull request is not open"}

    commits = api.paginate(f"/pulls/{safe_number}/commits")
    if len(commits) != 1:
        return {
            "pr": safe_number,
            "skipped": True,
            "reason": "repair requires exactly one untouched Dependabot source commit",
        }
    source_head = str((pull.get("head") or {}).get("sha") or "")
    base_sha = _current_main_sha(api, config)
    provenance = validate_provenance(pull, commits, base_sha, config, api.repository)
    if not provenance.get("eligible"):
        return {
            "pr": safe_number,
            "skipped": True,
            "reason": "canonical source provenance is not eligible",
            "reasons": provenance.get("reasons") or [],
        }

    files = api.paginate(f"/pulls/{safe_number}/files")
    if classify_ecosystem(files, config) != "docker":
        return {"pr": safe_number, "skipped": True, "reason": "not a Docker dependency proposal"}
    metadata = parse_dependabot_metadata(str(((commits[0].get("commit") or {}).get("message")) or ""))
    semantic = validate_docker(files, metadata, config)
    if not semantic.get("eligible"):
        return {
            "pr": safe_number,
            "skipped": True,
            "reason": "Docker dependency semantics are not eligible",
            "reasons": semantic.get("reasons") or [],
        }

    changes = semantic.get("changes") or []
    k6_changes = [
        change
        for change in changes
        if change.get("dependency") == "grafana/k6"
        and change.get("fromTag") != change.get("toTag")
    ]
    if not k6_changes:
        return {"pr": safe_number, "skipped": True, "reason": "no k6 release-marker repair required"}
    if len(changes) != 1 or len(k6_changes) != 1:
        raise GovernanceError("k6 source repair requires a single-dependency marker update")

    change = k6_changes[0]
    old_version = str(change["fromTag"])
    new_version = str(change["toTag"])
    current_text = api.file_at("docker/Dockerfile", source_head)
    if current_text is None:
        raise GovernanceError("Dockerfile is missing at Dependabot source head")
    new_commit = _resolve_k6_release_commit(api, new_version)
    updated = synchronize_dockerfile(
        current_text,
        old_version=old_version,
        new_version=new_version,
        new_commit=new_commit,
    )
    branch = str((pull.get("head") or {}).get("ref") or "")
    repair_sha = _publish_repair(
        api,
        branch=branch,
        source_head=source_head,
        dockerfile=updated,
    )
    return {
        "pr": safe_number,
        "skipped": False,
        "sourceHead": source_head,
        "repairHead": repair_sha,
        "k6Version": new_version,
        "k6Commit": new_commit,
    }


def _target_numbers(api: GitHubApi, config: dict[str, Any]) -> list[int]:
    direct = os.environ.get("TARGET_PR_NUMBER", "").strip()
    if direct:
        return [parse_positive_integer(direct, "TARGET_PR_NUMBER")]
    pulls = api.paginate(
        f"/pulls?state=open&base={urllib.parse.quote(config['baseBranch'], safe='')}"
    )
    return [
        int(pull["number"])
        for pull in pulls
        if isinstance(pull.get("number"), int)
        and (pull.get("user") or {}).get("login") == config["botLogin"]
        and (pull.get("user") or {}).get("id") == config["botUserId"]
    ]


def main() -> int:
    config = load_config()
    if config.get("baseBranch") != TRUSTED_BASE_BRANCH:
        raise GovernanceError("dependency repair baseBranch must remain literal main")
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    api = GitHubApi(token, repository, config["maxPaginationPages"])
    results: list[dict[str, Any]] = []
    for number in _target_numbers(api, config):
        try:
            results.append(repair_pull(api, number, config))
        except GovernanceError as exc:
            results.append({"pr": number, "error": str(exc)})
    print(json.dumps({"repairs": results}, indent=2, sort_keys=True))
    if any("error" in result for result in results):
        raise GovernanceError("one or more deterministic dependency repairs failed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GovernanceError as exc:
        print(f"dependency repair failed: {exc}", file=os.sys.stderr)
        raise SystemExit(1) from None
