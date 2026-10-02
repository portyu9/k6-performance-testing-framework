from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .github import parse_dependabot_metadata
from .models import unique

PUBLISHER_BOT_LOGIN = "github-actions[bot]"
PUBLISHER_BOT_USER_ID = 41898282
PUBLISHER_BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"
REPAIR_MESSAGE = "chore: synchronize k6 source provenance"

def validate_provenance(
    pull: dict[str, Any],
    commits: list[dict[str, Any]],
    base_sha: str,
    config: dict[str, Any],
    repository: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    reasons: list[str] = []
    now = now or datetime.now(timezone.utc)
    user = pull.get("user") or {}
    if user.get("login") != config["botLogin"]:
        reasons.append(f"PR author is {user.get('login') or 'unknown'}, not {config['botLogin']}")
    if user.get("id") != config["botUserId"]:
        reasons.append(
            f"PR author numeric identity is {user.get('id', 'unknown')}, expected {config['botUserId']}"
        )
    if pull.get("state") != "open":
        reasons.append("PR is not open")
    if pull.get("draft"):
        reasons.append("draft PRs are never autonomously merged")
    if config.get("automergeEnabled") is not True:
        reasons.append("repository autonomous merge kill switch is disabled")

    base = pull.get("base") or {}
    head = pull.get("head") or {}
    if base.get("ref") != config["baseBranch"]:
        reasons.append(f"base branch is {base.get('ref')}, expected {config['baseBranch']}")
    if (base.get("repo") or {}).get("full_name") != repository:
        reasons.append("base repository is not the governed repository")
    if (head.get("repo") or {}).get("full_name") != repository:
        reasons.append("Dependabot PR head must be in the governed repository")
    if not str(head.get("ref") or "").startswith("dependabot/"):
        reasons.append("head branch is not a Dependabot branch")

    labels = {
        label if isinstance(label, str) else label.get("name")
        for label in (pull.get("labels") or [])
    }
    for label in config["manualReviewLabels"]:
        if label in labels:
            reasons.append(f"PR carries manual-review label {label}")

    try:
        created_at = datetime.fromisoformat(str(pull.get("created_at")).replace("Z", "+00:00"))
        age_days = (now - created_at.astimezone(timezone.utc)).total_seconds() / 86400
        if age_days < 0:
            reasons.append("PR creation time is in the future")
        elif age_days > config["maxPullRequestAgeDays"]:
            reasons.append(
                f"PR age {age_days:.1f}d exceeds {config['maxPullRequestAgeDays']}d autonomous limit"
            )
    except (TypeError, ValueError):
        reasons.append("PR created_at is invalid")

    if len(commits) not in {1, 2}:
        reasons.append(
            f"expected one untouched Dependabot commit or one trusted repair commit, found {len(commits)}"
        )
        return {"eligible": False, "reasons": unique(reasons), "provenanceState": "untrusted"}

    source = commits[0]
    repair = commits[1] if len(commits) == 2 else None
    head_sha = str(head.get("sha") or "")
    source_sha = str(source.get("sha") or "")
    expected_head = str((repair or source).get("sha") or "")
    if expected_head != head_sha:
        reasons.append("final governed commit SHA does not equal current PR head")

    parents = source.get("parents") or []
    if len(parents) != 1 or (parents[0] or {}).get("sha") != base_sha:
        reasons.append("Dependabot commit parent is not the current main SHA")

    git = source.get("commit") or {}
    author = git.get("author") or {}
    committer = git.get("committer") or {}
    if author.get("email") != config["botAuthorEmail"]:
        reasons.append("Git author email is not the canonical Dependabot identity")
    top_author = source.get("author") or {}
    if top_author.get("login") != config["botLogin"] or top_author.get("id") != config["botUserId"]:
        reasons.append("materialized commit author is not the canonical Dependabot account")
    top_committer = source.get("committer") or {}
    if top_committer.get("login") != config["trustedCommitterLogin"]:
        reasons.append("materialized commit committer is not GitHub web-flow")
    if committer.get("name") != config["gitCommitterName"]:
        reasons.append("Git committer name is not canonical GitHub")
    if committer.get("email") != config["gitCommitterEmail"]:
        reasons.append("Git committer email is not canonical GitHub")

    verification = git.get("verification") or {}
    if verification.get("verified") is not True:
        reasons.append("Dependabot commit signature is not verified")
    if verification.get("reason") != "valid":
        reasons.append(
            f"Dependabot signature reason is {verification.get('reason') or 'unknown'}, not valid"
        )
    if not str(verification.get("signature") or "").strip():
        reasons.append("verified signature material is missing")
    if not str(verification.get("payload") or "").strip():
        reasons.append("verified signature payload is missing")
    message = str(git.get("message") or "")
    if config["signedOffBy"] not in message.splitlines():
        reasons.append("canonical Dependabot Signed-off-by trailer is missing")
    if not parse_dependabot_metadata(message):
        reasons.append("signed Dependabot updated-dependencies metadata is missing")

    provenance_state = "canonical-dependabot"
    if repair is not None:
        provenance_state = "canonical-dependabot-plus-repair"
        repair_git = repair.get("commit") or {}
        repair_author = repair.get("author") or {}
        repair_committer = repair.get("committer") or {}
        repair_git_author = repair_git.get("author") or {}
        repair_git_committer = repair_git.get("committer") or {}
        repair_verification = repair_git.get("verification") or {}
        repair_parents = repair.get("parents") or []
        expected_message = (
            f"{REPAIR_MESSAGE}\n\n"
            f"Generated from Dependabot source head {source_sha} by trusted default-branch "
            "dependency-repair."
        )
        if repair_author.get("login") != PUBLISHER_BOT_LOGIN or repair_author.get("id") != PUBLISHER_BOT_USER_ID:
            reasons.append("repair commit author is not canonical github-actions[bot]")
        if repair_committer.get("login") != config["trustedCommitterLogin"]:
            reasons.append("repair commit was not materialized by trusted GitHub web-flow")
        if (
            repair_git_author.get("name") != PUBLISHER_BOT_LOGIN
            or repair_git_author.get("email") != PUBLISHER_BOT_EMAIL
        ):
            reasons.append("repair Git author identity is not canonical github-actions[bot]")
        if (
            repair_git_committer.get("name") != config["gitCommitterName"]
            or repair_git_committer.get("email") != config["gitCommitterEmail"]
        ):
            reasons.append("repair Git committer identity does not match GitHub signing infrastructure")
        if repair_verification.get("verified") is not True or repair_verification.get("reason") != "valid":
            reasons.append("repair commit signature is not GitHub-verified as valid")
        if not str(repair_verification.get("signature") or "").strip():
            reasons.append("repair commit has no verifiable signature material")
        if len(repair_parents) != 1 or (repair_parents[0] or {}).get("sha") != source_sha:
            reasons.append("repair commit is not parented directly on the Dependabot source commit")
        if str(repair_git.get("message") or "") != expected_message:
            reasons.append("repair commit message does not bind the exact Dependabot source head")

    return {
        "eligible": not reasons,
        "reasons": unique(reasons),
        "provenanceState": provenance_state,
        "sourceCommit": source_sha,
        "repairCommit": str((repair or {}).get("sha") or "") or None,
    }


def validate_manual_path_scope(files: list[dict[str, Any]], config: dict[str, Any]) -> list[str]:
    manual = set(str(path) for path in config["manualReviewPaths"])
    return [
        f"control-plane path {name} always requires manual review"
        for name in (str(file.get("filename", "")) for file in files)
        if name in manual
    ]


def validate_docker_manual(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "eligible": False,
        "reasons": [str(config["ecosystems"]["docker"]["reason"])],
        "changes": [],
    }
