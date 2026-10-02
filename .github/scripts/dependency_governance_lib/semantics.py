from __future__ import annotations

import re
from typing import Any

from .github import GitHubApi
from .models import ACTION_LINE, GO_SUM_LINE, normalize_version, semver_tuple, unique
from .provenance import validate_manual_path_scope


def parse_override_go_mod(
    text: str,
    config: dict[str, Any],
) -> tuple[str, str, dict[str, str], dict[str, str]] | None:
    """Parse direct override authority while retaining indirect metadata for equality proof."""
    module = ""
    go_version = ""
    versions: dict[str, str] = {}
    indirect_versions: dict[str, str] = {}
    seen_modules: set[str] = set()
    in_require_block = False
    dependencies = {
        str(value) for value in config["ecosystems"]["gomod-security-override"]["dependencies"]
    }

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        if line.startswith("module "):
            if in_require_block or module or len(line.split()) != 2:
                return None
            module = line.removeprefix("module ").strip()
            continue
        if line.startswith("go "):
            if in_require_block or go_version or len(line.split()) != 2:
                return None
            go_version = line.removeprefix("go ").strip()
            continue
        if line == "require (":
            if in_require_block:
                return None
            in_require_block = True
            continue
        if line == ")":
            if not in_require_block:
                return None
            in_require_block = False
            continue

        parts = line.split()
        if not in_require_block:
            if not parts or parts[0] != "require":
                return None
            parts = parts[1:]
        if len(parts) not in {2, 4}:
            return None
        name, version = parts[0], parts[1]
        indirect = len(parts) == 4 and parts[2:] == ["//", "indirect"]
        if len(parts) == 4 and not indirect:
            return None
        if not re.fullmatch(r"v\d+\.\d+\.\d+", version):
            return None
        if name in seen_modules:
            return None
        seen_modules.add(name)
        if indirect:
            if name in dependencies:
                return None
            indirect_versions[name] = version
            continue
        if name not in dependencies:
            return None
        versions[name] = version

    expected_module = str(config["ecosystems"]["gomod-security-override"]["module"])
    if in_require_block or module != expected_module or not go_version or set(versions) != dependencies:
        return None
    return module, go_version, versions, indirect_versions


def validate_go_override(
    api: GitHubApi,
    base_sha: str,
    head_sha: str,
    files: list[dict[str, Any]],
    metadata: list[dict[str, str]],
    config: dict[str, Any],
) -> dict[str, Any]:
    reasons = validate_manual_path_scope(files, config)
    policy = config["ecosystems"]["gomod-security-override"]
    allowed_files = set(policy["files"])
    names = {str(file.get("filename", "")) for file in files}
    go_mod = "docker/security-overrides/go.mod"
    if go_mod not in names:
        reasons.append("Go security override update must change go.mod")
    unexpected = sorted(name for name in names if name not in allowed_files)
    if unexpected:
        reasons.append("unexpected Go override files: " + ", ".join(unexpected))

    base_text = api.file_at(go_mod, base_sha)
    head_text = api.file_at(go_mod, head_sha)
    if base_text is None or head_text is None:
        reasons.append("Go security override go.mod must exist at base and head")
        return {"eligible": False, "reasons": unique(reasons), "changes": []}
    base_model = parse_override_go_mod(base_text, config)
    head_model = parse_override_go_mod(head_text, config)
    if not base_model or not head_model:
        reasons.append("Go security override go.mod shape is outside the governed minimal model")
        return {"eligible": False, "reasons": unique(reasons), "changes": []}
    if base_model[:2] != head_model[:2]:
        reasons.append("module path and Go language version must remain unchanged")
    if base_model[3] != head_model[3]:
        reasons.append("indirect Go module metadata must remain unchanged in autonomous override updates")

    dependencies = [str(value) for value in policy["dependencies"]]
    changes: list[dict[str, str]] = []
    for dependency in dependencies:
        old_text = base_model[2][dependency]
        new_text = head_model[2][dependency]
        if old_text == new_text:
            continue
        old_version = semver_tuple(old_text)
        new_version = semver_tuple(new_text)
        if not old_version or not new_version:
            reasons.append(f"{dependency} override versions must be strict semantic versions")
        elif new_version[0] != old_version[0] or new_version <= old_version:
            reasons.append(
                f"{dependency} autonomous security override updates must increase within the same major line"
            )
        changes.append({"dependency": dependency, "from": old_text, "to": new_text})

    if not changes:
        reasons.append("Go security override PR does not change an allowlisted dependency version")

    metadata_by_name: dict[str, dict[str, str]] = {}
    for item in metadata:
        name = str(item.get("name") or "")
        if not name or name in metadata_by_name:
            reasons.append("signed Go override metadata contains missing or duplicate dependency names")
            continue
        metadata_by_name[name] = item
    changed_dependencies = {change["dependency"] for change in changes}
    if set(metadata_by_name) != changed_dependencies:
        reasons.append("signed Go override metadata does not exactly match changed dependencies")
    for change in changes:
        dependency = change["dependency"]
        item = metadata_by_name.get(dependency)
        if not item:
            continue
        if item.get("dependencyType") != "direct:production":
            reasons.append(f"{dependency} signed dependency type must be direct:production")
        update_type = str(item.get("updateType") or "")
        if update_type not in config["allowedGoOverrideUpdateTypes"]:
            reasons.append(
                f"{dependency} Go override update type {update_type or 'unknown'} is not autonomous"
            )
        old_version = semver_tuple(change["from"])
        new_version = semver_tuple(change["to"])
        if old_version and new_version:
            if "semver-patch" in update_type and new_version[:2] != old_version[:2]:
                reasons.append(f"{dependency} signed patch metadata does not describe a patch-only change")
            if "semver-minor" in update_type and (
                new_version[0] != old_version[0] or new_version[1] <= old_version[1]
            ):
                reasons.append(f"{dependency} signed minor metadata does not describe a minor-line increase")
        if normalize_version(item.get("version", "")) != normalize_version(change["to"]):
            reasons.append(f"{dependency} signed dependency-version does not match head go.mod")

    go_sum = "docker/security-overrides/go.sum"
    if go_sum in names:
        head_sum = api.file_at(go_sum, head_sha, optional=True)
        if head_sum is None:
            reasons.append("changed go.sum is missing at head")
        else:
            bad_lines = [
                line
                for line in head_sum.splitlines()
                if line.strip() and not GO_SUM_LINE.fullmatch(line.strip())
            ]
            if bad_lines:
                reasons.append("go.sum contains non-checksum content")
            lines = [line.strip() for line in head_sum.splitlines() if line.strip()]
            if len(lines) != len(set(lines)):
                reasons.append("go.sum contains duplicate checksum lines")

    return {"eligible": not reasons, "reasons": unique(reasons), "changes": changes}


def action_diff_pairs(patch: str) -> tuple[list[tuple[re.Match[str], re.Match[str]]], list[str]]:
    removed: list[re.Match[str]] = []
    added: list[re.Match[str]] = []
    reasons: list[str] = []
    for line in str(patch or "").splitlines():
        if line.startswith(("@@", "---", "+++")):
            continue
        if line.startswith("-"):
            match = ACTION_LINE.fullmatch(line[1:])
            if not match:
                reasons.append("removed workflow content is not an immutable uses: line")
            else:
                removed.append(match)
        elif line.startswith("+"):
            match = ACTION_LINE.fullmatch(line[1:])
            if not match:
                reasons.append("added workflow content is not an immutable uses: line")
            else:
                added.append(match)
    if not removed or len(removed) != len(added):
        reasons.append("workflow update must replace immutable uses: lines one-for-one")
        return [], unique(reasons)
    pairs: list[tuple[re.Match[str], re.Match[str]]] = []
    for old, new in zip(removed, added, strict=True):
        if old.group("action") != new.group("action"):
            reasons.append("workflow update may not replace one action with another")
        if old.group("ref").lower() == new.group("ref").lower():
            reasons.append("workflow action SHA replacement did not change the SHA")
        if old.group("prefix") != new.group("prefix"):
            reasons.append("workflow action replacement changed line structure")
        pairs.append((old, new))
    return pairs, unique(reasons)


def validate_actions(
    files: list[dict[str, Any]],
    metadata: list[dict[str, str]],
    config: dict[str, Any],
) -> dict[str, Any]:
    # A canonical Dependabot action-only diff is itself the reviewed semantic boundary.
    # Mixed edits fail below because every +/- line must be an immutable uses replacement.
    reasons: list[str] = []
    changes: list[dict[str, str]] = []
    for file in files:
        filename = str(file.get("filename", ""))
        patch = file.get("patch")
        if not isinstance(patch, str) or not patch.strip():
            reasons.append(f"workflow patch is unavailable for {filename}; refusing ambiguous update")
            continue
        pairs, pair_reasons = action_diff_pairs(patch)
        reasons.extend(f"{filename}: {reason}" for reason in pair_reasons)
        for old, new in pairs:
            changes.append(
                {
                    "file": filename,
                    "action": new.group("action"),
                    "fromSha": old.group("ref").lower(),
                    "toSha": new.group("ref").lower(),
                    "version": new.group("version"),
                }
            )
    if not changes:
        reasons.append("no immutable GitHub Action SHA updates were proven")

    metadata_by_name: dict[str, dict[str, str]] = {}
    for item in metadata:
        name = item.get("name", "")
        if not name or name in metadata_by_name:
            reasons.append("signed action metadata contains missing or duplicate dependency names")
            continue
        metadata_by_name[name] = item
    changed_actions = {change["action"] for change in changes}
    if set(metadata_by_name) != changed_actions:
        reasons.append("signed dependency metadata does not exactly match changed GitHub Actions")
    for action in sorted(changed_actions):
        item = metadata_by_name.get(action)
        action_changes = [change for change in changes if change["action"] == action]
        versions = {normalize_version(change["version"]) for change in action_changes}
        if len(versions) != 1:
            reasons.append(f"{action} has inconsistent version annotations across workflow files")
        if not item:
            continue
        if item.get("updateType") not in config["allowedActionUpdateTypes"]:
            reasons.append(f"{action} update type {item.get('updateType') or 'unknown'} is not autonomous")
        signed_version = normalize_version(item.get("version", ""))
        if versions and signed_version not in versions:
            reasons.append(f"{action} signed dependency-version does not match the workflow annotation")
        version = semver_tuple(signed_version)
        if not version:
            reasons.append(f"{action} signed version is not strict semantic version metadata")
        elif version[0] == 0 and "minor" in str(item.get("updateType", "")):
            reasons.append(f"{action} 0.x minor updates remain manual breaking-risk changes")

    return {"eligible": not reasons, "reasons": unique(reasons), "changes": changes}


DOCKER_FROM_LINE = re.compile(
    r"^(?P<prefix>\s*FROM\s+(?:(?P<platform>--platform=\S+)\s+)?)"
    r"(?P<image>[A-Za-z0-9_.\/-]+):(?P<tag>[^@\s]+)"
    r"@sha256:(?P<digest>[0-9a-f]{64})"
    r"(?P<suffix>\s+AS\s+(?P<alias>[A-Za-z0-9_.-]+)\s*)$"
)
K6_VERSION_ARG = re.compile(r"^ARG K6_VERSION=(?P<value>\d+\.\d+\.\d+)$")
K6_COMMIT_ARG = re.compile(r"^ARG K6_COMMIT=(?P<value>[0-9a-f]{40})$")


def _docker_semver(tag: str) -> tuple[int, int, int] | None:
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$", tag)
    return tuple(int(value) for value in match.groups()) if match else None


def validate_docker(
    files: list[dict[str, Any]],
    metadata: list[dict[str, str]],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Allow immutable image updates plus the exact trusted k6 source-pin repair shape."""
    reasons: list[str] = []
    if [str(file.get("filename") or "") for file in files] != ["docker/Dockerfile"]:
        return {
            "eligible": False,
            "reasons": ["Docker dependency PR must change only docker/Dockerfile"],
            "changes": [],
        }

    patch = files[0].get("patch")
    if not isinstance(patch, str) or not patch.strip():
        return {
            "eligible": False,
            "reasons": ["Dockerfile patch is unavailable; refusing ambiguous update"],
            "changes": [],
        }

    removed_from: list[re.Match[str]] = []
    added_from: list[re.Match[str]] = []
    removed_version: list[re.Match[str]] = []
    added_version: list[re.Match[str]] = []
    removed_commit: list[re.Match[str]] = []
    added_commit: list[re.Match[str]] = []

    for line in patch.splitlines():
        if line.startswith(("@@", "---", "+++")):
            continue
        if not line.startswith(("-", "+")):
            continue
        value = line[1:]
        from_match = DOCKER_FROM_LINE.fullmatch(value)
        version_match = K6_VERSION_ARG.fullmatch(value)
        commit_match = K6_COMMIT_ARG.fullmatch(value)
        if line.startswith("-"):
            if from_match:
                removed_from.append(from_match)
            elif version_match:
                removed_version.append(version_match)
            elif commit_match:
                removed_commit.append(commit_match)
            else:
                reasons.append("removed Dockerfile content is outside the governed dependency repair shape")
        else:
            if from_match:
                added_from.append(from_match)
            elif version_match:
                added_version.append(version_match)
            elif commit_match:
                added_commit.append(commit_match)
            else:
                reasons.append("added Dockerfile content is outside the governed dependency repair shape")

    if not removed_from or len(removed_from) != len(added_from):
        reasons.append("Docker update must replace immutable FROM references one-for-one")
        return {"eligible": False, "reasons": unique(reasons), "changes": []}

    changes: list[dict[str, str]] = []
    for old, new in zip(removed_from, added_from, strict=True):
        if old.group("image") != new.group("image"):
            reasons.append("Docker update may not replace one image dependency with another")
        if old.group("platform") != new.group("platform") or old.group("alias") != new.group("alias"):
            reasons.append("Docker update may not change stage platform or alias")
        if old.group("prefix") != new.group("prefix") or old.group("suffix") != new.group("suffix"):
            reasons.append("Docker update changed FROM line structure")
        if old.group("tag") == new.group("tag") and old.group("digest") == new.group("digest"):
            reasons.append("Docker FROM replacement did not change tag or digest")
        changes.append(
            {
                "dependency": new.group("image"),
                "fromTag": old.group("tag"),
                "toTag": new.group("tag"),
                "fromDigest": old.group("digest"),
                "toDigest": new.group("digest"),
            }
        )

    allowed_dependencies = set(config["ecosystems"]["docker"]["dependencies"])
    changed_dependencies = {change["dependency"] for change in changes}
    if not changed_dependencies.issubset(allowed_dependencies):
        reasons.append("Docker update changes a dependency outside the explicit allowlist")

    metadata_by_name: dict[str, dict[str, str]] = {}
    for item in metadata:
        name = str(item.get("name") or "")
        if not name or name in metadata_by_name:
            reasons.append("signed Docker metadata contains missing or duplicate dependency names")
            continue
        metadata_by_name[name] = item
    if set(metadata_by_name) != changed_dependencies:
        reasons.append("signed Docker metadata does not exactly match changed image dependencies")

    for change in changes:
        dependency = change["dependency"]
        item = metadata_by_name.get(dependency)
        if not item:
            continue
        if item.get("dependencyType") != "direct:production":
            reasons.append(f"{dependency} signed dependency type must be direct:production")
        update_type = str(item.get("updateType") or "")
        if update_type not in config["allowedDockerUpdateTypes"]:
            reasons.append(f"{dependency} Docker update type {update_type or 'unknown'} is not autonomous")
        if str(item.get("version") or "") != change["toTag"]:
            reasons.append(f"{dependency} signed dependency-version does not match the new Docker tag")

        if change["fromTag"] != change["toTag"]:
            old_version = _docker_semver(change["fromTag"])
            new_version = _docker_semver(change["toTag"])
            if not old_version or not new_version:
                reasons.append(f"{dependency} tag change is not a supported semantic version")
            elif new_version[0] != old_version[0] or new_version <= old_version:
                reasons.append(f"{dependency} autonomous Docker update must increase within the same major line")
            elif "semver-patch" in update_type and new_version[:2] != old_version[:2]:
                reasons.append(f"{dependency} signed patch metadata does not describe a patch-only tag change")
            elif "semver-minor" in update_type and new_version[1] <= old_version[1]:
                reasons.append(f"{dependency} signed minor metadata does not describe a minor-line increase")

    repair_line_count = (
        len(removed_version) + len(added_version) + len(removed_commit) + len(added_commit)
    )
    if repair_line_count:
        k6_changes = [
            change
            for change in changes
            if change["dependency"] == "grafana/k6"
            and change["fromTag"] != change["toTag"]
        ]
        if (
            len(k6_changes) != 1
            or len(changes) != 1
            or len(removed_version) != 1
            or len(added_version) != 1
            or len(removed_commit) != 1
            or len(added_commit) != 1
        ):
            reasons.append("k6 source repair must pair one marker update with exactly two source-pin replacements")
        else:
            k6_change = k6_changes[0]
            if removed_version[0].group("value") != k6_change["fromTag"]:
                reasons.append("removed K6_VERSION does not match the previous k6 marker tag")
            if added_version[0].group("value") != k6_change["toTag"]:
                reasons.append("repaired K6_VERSION does not match the new k6 marker tag")
            if removed_commit[0].group("value") == added_commit[0].group("value"):
                reasons.append("repaired K6_COMMIT did not change")

    return {
        "eligible": not reasons,
        "reasons": unique(reasons),
        "changes": changes,
        "sourceRepair": bool(repair_line_count),
    }



def validate_semantics(
    api: GitHubApi,
    ecosystem: str,
    base_sha: str,
    head_sha: str,
    files: list[dict[str, Any]],
    metadata: list[dict[str, str]],
    config: dict[str, Any],
) -> dict[str, Any]:
    if len(files) > config["maxChangedFiles"]:
        return {
            "eligible": False,
            "reasons": [f"PR changes {len(files)} files; limit is {config['maxChangedFiles']}"],
            "changes": [],
        }
    if ecosystem == "docker":
        return validate_docker(files, metadata, config)
    if ecosystem == "gomod-security-override":
        return validate_go_override(api, base_sha, head_sha, files, metadata, config)
    if ecosystem == "github-actions":
        return validate_actions(files, metadata, config)
    return {
        "eligible": False,
        "reasons": ["changed-file scope does not match an autonomously governed dependency ecosystem"],
        "changes": [],
    }
