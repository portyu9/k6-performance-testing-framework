# Changelog

All notable public changes to this project are documented here.

The format is based on Keep a Changelog and the project uses semantic versioning for public release checkpoints.

## [Unreleased]

### Added

- Verified CI evidence surfaced in the README with an attributable successful run.
- Discovery-focused examples for smoke, arrival-rate workloads, thresholds, business metrics, GitHub Actions, Docker, and structured summaries.
- Search-oriented guides for k6 GitHub Actions, thresholds vs checks, and safe load testing.
- GitHub Pages-ready documentation landing page.
- Release process and prepared v1.0.0 release notes.

### Changed

- Runtime qualification now uses a patch-versioned, digest-pinned Alpine 3.24.2 image and verifies its baked OpenSSL libraries without a mutable final-stage package fetch.
- Repository-owned Go override metadata now uses the renamed canonical repository module path.
- Product positioning centers on **k6 Performance Testing Framework**.
- Repository identity uses the line **Safe by default. Evidence by design.**
- Workflow badge URLs use the renamed repository path.

## Release policy

See [`docs/RELEASING.md`](docs/RELEASING.md).
