# Release process

Public releases are checkpoints of reviewed evidence, not just tags.

## Versioning

Use semantic versioning:

- **major**: incompatible framework/runtime contract changes;
- **minor**: backward-compatible capabilities, profiles, evidence, or integrations;
- **patch**: backward-compatible fixes and documentation corrections.

## Release checklist

1. Merge the release scope through normal pull-request review.
2. Require `ci-gate`, `extended-gate`, `security-gate`, and documentation contracts to pass on the main-branch commit selected for release.
3. Confirm README/runtime provenance claims still match tracked manifests.
4. Move relevant entries from **Unreleased** in `CHANGELOG.md` into the versioned section.
5. Create an annotated `vX.Y.Z` tag from that reviewed main-branch commit.
6. Create the GitHub Release from the tag and use the prepared notes as a starting point.
7. Link the release to the exact CI/security evidence used for qualification.
8. Never create a release from an unmerged discoverability or feature branch.

## v1.0.0

Prepared notes live in [`releases/v1.0.0.md`](releases/v1.0.0.md). Publish only after the productization/discoverability changes are merged and the main-branch gates pass.
