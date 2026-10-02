# Dependabot qualification recovery

## Purpose

A dependency qualification failure can be a deterministic framework/security failure or a short-lived transport failure while publishing already-generated evidence. This repository distinguishes those cases without weakening any k6, container, provenance, or security gate.

`.github/scripts/dependency_recovery.py` may request one failed-job rerun only when the existing canonical Dependabot proposal, exact-head qualification run, failed job, failed step, and timestamp-bounded log evidence all satisfy the recovery policy. It never merges a pull request. `.github/scripts/dependency_repair.py` is a separate, narrower controller: for a canonical single-dependency k6 release-marker update it may append exactly one trusted GitHub-signed commit that synchronizes only `K6_VERSION` and `K6_COMMIT`. Dependency governance remains the only autonomous merge authority.

## Recovery boundary

`maxRunAttempts` is `2`, so the original run can receive at most one automatic retry. Recovery requires canonical `dependabot[bot]` numeric identity, signed dependency metadata, an exact governed dependency scope, and an exact-head pull-request workflow run. Provenance accepts either one verified GitHub-materialized Dependabot commit directly on current `main`, or that exact source commit followed by one GitHub-verified trusted repair commit whose parent, author, committer, message, and diff shape are all independently constrained.

The retry allowlist is deliberately narrower than the framework's dependency surface. Only these evidence-transport steps are eligible: `Upload k6 summary`, `Upload extended evidence`, `Upload repository security evidence`, and `Upload container security evidence`. A failed upload must contain a recognized transient network/service signature inside that exact step's timestamp window.

Docker builds, k6 smoke execution, zero-traffic sustained-profile inspection, provenance validation, threshold/evidence validation, CodeQL, Trivy scanning, Dependency Review, and aggregate gates are never recovery steps. Missing artifact files are deterministic evidence failures and explicitly block recovery.

## Dependency semantics remain authoritative

Recovery does not relax dependency semantics. GitHub Actions proposals must still satisfy the immutable-SHA/action metadata policy; canonical action-only Dependabot replacements can qualify even in otherwise protected workflow files because every changed line is proven to be a one-for-one immutable `uses:` replacement, while any mixed workflow edit fails closed. Go security-override proposals must still satisfy the exact constrained `go.mod`/`go.sum`, dependency-name, signed-metadata, unchanged indirect-module metadata, and no-major-update policy before recovery is eligible. Patch and minor updates may qualify only after the complete exact-head gate set passes.

Docker proposals are autonomously eligible only when canonical Dependabot provenance proves a one-for-one immutable `FROM` reference update for an allowlisted image, signed metadata matches the new tag, no major line is crossed, and the complete exact-head gate set passes. k6 release-marker updates additionally require trusted deterministic source-provenance repair.

## Deterministic failures win

Within an allowlisted upload step, deterministic evidence is evaluated before transient strings. Missing artifact files, client/policy HTTP 400/401/403/404/409/422/429 responses, permission failures, and disk exhaustion prevent recovery even if the same step also contains a transient-looking message.

Recognized transient evidence is narrow: DNS retry/resolution failures, connection resets/timeouts, unreachable network or host errors, socket timeouts/hangups, contextual HTTP 502/503/504 responses, exact gateway/service-outage responses, and bounded TLS timeout/unexpected-EOF failures. Generic `Service Unavailable` text without attributable status context is not enough.

## Native rebasing and authority separation

All three Dependabot ecosystems use `rebase-strategy: auto`. If a canonical proposal is stale, the trusted controller posts an idempotent `@dependabot rebase` request at most once per current `main` SHA; it never calls GitHub `update-branch` and never rewrites the branch itself. The hourly reconciliation sweep is the backstop when no workflow event arrives.

The deterministic k6 source repair is the only controlled branch-write exception. Its commit message contains `[dependabot skip]`, which GitHub documents as the opt-in that allows Dependabot to rebase and force-push over an extra commit. A later native rebase may therefore replace the repair; if the k6 marker still requires synchronization, trusted repair is re-derived from the new canonical source head. The marker is for Dependabot branch ownership, not a GitHub Actions CI-skip token.

Recovery configuration/code, governance configuration/code/library, the governance workflow, and `.github/dependabot.yml` are manual-review control-plane paths for ordinary changes. Pull-request self-tests run read-only. Only trusted default-branch governance code holds write permissions for the bounded rebase request, deterministic k6 repair, failed-job retry, status comment, and exact-head merge.

A successful retry is not merge evidence. The normal exact-head CI, Extended, Security, and Docs workflows must complete successfully; dependency governance then independently re-proves provenance, semantics, and every stable aggregate gate before any eligible autonomous merge.
