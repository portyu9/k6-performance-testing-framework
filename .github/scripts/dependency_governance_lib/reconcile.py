from __future__ import annotations

import urllib.parse
from typing import Any

from .github import GitHubApi
from .models import Assessment, GovernanceError
from .qualification import fetch_assessment

OWNER_REVIEW_MARKER = "<!-- dependency-owner-review:v1:"
OWNER_APPROVAL_MARKER = "<!-- dependency-owner-approval:v1:"
OWNER_REFRESH_MARKER = "<!-- dependency-owner-refresh:v2:"


def verify_owner_identity(owner_api: GitHubApi | None, config: dict[str, Any]) -> dict[str, Any]:
    if owner_api is None:
        raise GovernanceError(
            "DEPENDABOT_OWNER_TOKEN is required for owner-authenticated Dependabot refresh, review, and approval"
        )
    identity = owner_api.get("https://api.github.com/user")
    if not isinstance(identity, dict):
        raise GovernanceError("owner token identity response is invalid")
    if (
        identity.get("login") != config["ownerApprovalLogin"]
        or identity.get("id") != config["ownerApprovalUserId"]
    ):
        raise GovernanceError(
            "DEPENDABOT_OWNER_TOKEN does not authenticate the configured repository owner identity"
        )
    return identity


def has_exact_owner_approval(
    owner_api: GitHubApi,
    number: int,
    head_sha: str,
    config: dict[str, Any],
) -> bool:
    reviews = owner_api.paginate(f"/pulls/{number}/reviews")
    return any(
        review.get("state") == "APPROVED"
        and review.get("commit_id") == head_sha
        and (review.get("user") or {}).get("login") == config["ownerApprovalLogin"]
        and (review.get("user") or {}).get("id") == config["ownerApprovalUserId"]
        for review in reviews
    )


def ensure_owner_review_and_approval(
    owner_api: GitHubApi | None,
    assessment: Assessment,
    config: dict[str, Any],
) -> None:
    verify_owner_identity(owner_api, config)
    assert owner_api is not None
    number = int(assessment.pull["number"])
    head_sha = assessment.head_sha

    comment_marker = f"{OWNER_REVIEW_MARKER}{head_sha} -->"
    comments = owner_api.paginate(f"/issues/{number}/comments")
    owner_comments = [
        comment
        for comment in comments
        if comment_marker in str(comment.get("body") or "")
        and (comment.get("user") or {}).get("login") == config["ownerApprovalLogin"]
        and (comment.get("user") or {}).get("id") == config["ownerApprovalUserId"]
    ]
    if len(owner_comments) > 1:
        raise GovernanceError(f"PR #{number} has duplicate exact-head owner review comments")
    if not owner_comments:
        owner_api.post(
            f"/issues/{number}/comments",
            {
                "body": (
                    f"{comment_marker}\n"
                    "## Owner-authenticated Dependabot review\n\n"
                    f"- Exact head: `{head_sha}`\n"
                    "- Canonical Dependabot provenance: **pass**\n"
                    "- Semantic dependency scope: **pass**\n"
                    "- Exact-head CI / Extended / Security / Docs qualification: **pass**\n"
                    "- Action: approve this exact head, revalidate it, then merge only if it remains unchanged and qualified.\n"
                )
            },
        )

    if not has_exact_owner_approval(owner_api, number, head_sha, config):
        approval_marker = f"{OWNER_APPROVAL_MARKER}{head_sha} -->"
        owner_api.post(
            f"/pulls/{number}/reviews",
            {
                "event": "APPROVE",
                "commit_id": head_sha,
                "body": (
                    f"{approval_marker}\n"
                    "Owner-authenticated automated approval for this exact Dependabot head after "
                    "canonical provenance, governed semantic scope, and all required exact-head "
                    "qualification gates passed. Repository rules remain authoritative."
                ),
            },
        )
    if not has_exact_owner_approval(owner_api, number, head_sha, config):
        raise GovernanceError(f"PR #{number} does not have the required exact-head owner approval")


def render_status(assessment: Assessment, decision: str, extra: list[str] | None = None) -> str:
    marker = "<!-- dependency-governance:v1 -->"
    reasons = assessment.reasons + list(extra or [])
    lines = [
        marker,
        "## Dependency governance",
        "",
        f"- Decision: **{decision}**",
        f"- Ecosystem: `{assessment.ecosystem}`",
        f"- Exact head: `{assessment.head_sha or 'unknown'}`",
        f"- Current base: `{assessment.base_sha}`",
        f"- Canonical Dependabot provenance: **{'pass' if assessment.provenance.get('eligible') else 'block'}**",
        f"- Semantic dependency scope: **{'pass' if assessment.semantic.get('eligible') else 'block'}**",
        f"- Exact-head workflow qualification: **{'pass' if assessment.qualification.get('eligible') else 'block'}**",
    ]
    changes = assessment.semantic.get("changes") or []
    if changes:
        lines.extend(["", "Proven semantic changes:"])
        for change in changes[:20]:
            if "action" in change:
                lines.append(f"- `{change['action']}` -> `{change['version']}` in `{change['file']}`")
            else:
                lines.append(f"- `{change.get('dependency')}`: `{change.get('from')}` -> `{change.get('to')}`")
    if reasons:
        lines.extend(["", "Blocking reasons:"])
        lines.extend(f"- {reason}" for reason in reasons[:30])
    lines.extend(
        [
            "",
            "Privileged reconciliation executes only trusted default-branch governance code; pull-request code is never executed with write permissions.",
        ]
    )
    return "\n".join(lines) + "\n"


def upsert_status_comment(api: GitHubApi, number: int, body: str, config: dict[str, Any]) -> None:
    comments = api.paginate(f"/issues/{number}/comments")
    marker = str(config["statusCommentMarker"])
    matches = [comment for comment in comments if marker in str(comment.get("body") or "")]
    if len(matches) > 1:
        raise GovernanceError(
            f"PR #{number} has {len(matches)} governance status comments; refusing ambiguous update"
        )
    if matches:
        api.patch(f"/issues/comments/{matches[0]['id']}", {"body": body})
    else:
        api.post(f"/issues/{number}/comments", {"body": body})


def request_dependabot_refresh(
    owner_api: GitHubApi | None,
    number: int,
    assessment: Assessment,
    config: dict[str, Any],
) -> str | None:
    """Request native Dependabot regeneration only through the configured push-capable owner."""
    stale = "Dependabot commit parent is not the current main SHA"
    if stale not in assessment.provenance.get("reasons", []):
        return None
    verify_owner_identity(owner_api, config)
    assert owner_api is not None
    state = str(assessment.provenance.get("provenanceState") or "")
    command = "recreate" if state == "canonical-dependabot-plus-repair" else "rebase"
    marker = f"{OWNER_REFRESH_MARKER}{assessment.head_sha}:{command} -->"
    comments = owner_api.paginate(f"/issues/{number}/comments")
    if any(
        marker in str(comment.get("body") or "")
        and (comment.get("user") or {}).get("login") == config["ownerApprovalLogin"]
        and (comment.get("user") or {}).get("id") == config["ownerApprovalUserId"]
        for comment in comments
    ):
        return command
    owner_api.post(
        f"/issues/{number}/comments",
        {
            "body": (
                f"@dependabot {command}\n\n"
                f"{marker}\n"
                "Requested by the configured push-capable repository owner because the exact "
                "Dependabot source commit is no longer parented on current main. Qualification "
                "restarts on the new exact head; no merge or security gate is bypassed."
            )
        },
    )
    return command



def dispatch_main_qualification(api: GitHubApi, config: dict[str, Any]) -> None:
    failures: list[str] = []
    for expected in config["requiredWorkflows"]:
        try:
            api.post(
                f"/actions/workflows/{urllib.parse.quote(expected['file'], safe='')}/dispatches",
                {"ref": config["baseBranch"]},
            )
        except GovernanceError as exc:
            failures.append(f"{expected['workflow']}: {exc}")
    if failures:
        raise GovernanceError(
            "post-merge main qualification dispatch failed for " + "; ".join(failures)
        )


def merge_exact_head(
    api: GitHubApi,
    owner_api: GitHubApi | None,
    assessment: Assessment,
    config: dict[str, Any],
) -> dict[str, Any]:
    number = int(assessment.pull["number"])
    refreshed = fetch_assessment(api, number, config)
    if refreshed.head_sha != assessment.head_sha:
        raise GovernanceError("PR head changed during pre-merge refresh")
    if refreshed.base_sha != assessment.base_sha:
        raise GovernanceError("main changed during pre-merge refresh")
    if not refreshed.eligible:
        return {"merged": False, "assessment": refreshed}
    verify_owner_identity(owner_api, config)
    assert owner_api is not None
    if not has_exact_owner_approval(owner_api, number, refreshed.head_sha, config):
        raise GovernanceError("exact-head owner approval disappeared before merge")
    result = api.put(
        f"/pulls/{number}/merge",
        {
            "sha": refreshed.head_sha,
            "merge_method": config["mergeMethod"],
            "commit_title": str(refreshed.pull.get("title") or "Dependabot qualified update"),
            "commit_message": (
                "Autonomously merged by the repository dependency-governance policy after "
                "canonical Dependabot provenance, semantic dependency validation, and exact-head "
                "CI/Extended/Security/Docs qualification were revalidated immediately before merge."
            ),
        },
    )
    if not isinstance(result, dict) or result.get("merged") is not True:
        raise GovernanceError(f"GitHub rejected exact-head merge for PR #{number}: {result}")
    return {"merged": True, "assessment": refreshed, "result": result}


def reconcile_one(
    api: GitHubApi,
    owner_api: GitHubApi | None,
    number: int,
    config: dict[str, Any],
    allow_merge: bool,
) -> str:
    pull = api.get(f"/pulls/{number}")
    user = pull.get("user") or {}
    if user.get("login") != config["botLogin"]:
        return f"PR #{number}: ignored non-Dependabot pull request"
    assessment = fetch_assessment(api, number, config)
    if not assessment.eligible:
        refresh = request_dependabot_refresh(owner_api, number, assessment, config)
        decision = f"native Dependabot {refresh} requested" if refresh else "manual review required"
        upsert_status_comment(api, number, render_status(assessment, decision), config)
        if refresh:
            return f"PR #{number}: requested Dependabot {refresh} for stale exact head {assessment.head_sha}"
        return f"PR #{number}: blocked ({'; '.join(assessment.reasons[:3])})"
    if not allow_merge:
        upsert_status_comment(api, number, render_status(assessment, "qualified; merge deferred"), config)
        return f"PR #{number}: qualified; merge deferred"

    ensure_owner_review_and_approval(owner_api, assessment, config)
    merged = merge_exact_head(api, owner_api, assessment, config)
    refreshed: Assessment = merged["assessment"]
    if not merged["merged"]:
        upsert_status_comment(api, number, render_status(refreshed, "manual review required"), config)
        return f"PR #{number}: pre-merge refresh blocked"

    dispatch_errors: list[str] = []
    try:
        dispatch_main_qualification(api, config)
    except GovernanceError as exc:
        dispatch_errors.append(str(exc))
    decision = "merged; main requalification dispatched" if not dispatch_errors else "merged; post-merge dispatch failed"
    try:
        upsert_status_comment(api, number, render_status(refreshed, decision, dispatch_errors), config)
    except GovernanceError as exc:
        dispatch_errors.append(f"status comment update failed after merge: {exc}")
    if dispatch_errors:
        raise GovernanceError("; ".join(dispatch_errors))
    return f"PR #{number}: merged exact head {refreshed.head_sha}"

