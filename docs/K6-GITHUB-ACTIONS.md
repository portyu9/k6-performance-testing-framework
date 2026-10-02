---
title: Running k6 Performance Tests in GitHub Actions Safely
description: A production CI pattern for k6 smoke, load, stress, and soak testing with explicit traffic boundaries and machine-readable evidence.
---

# Running k6 Performance Tests in GitHub Actions Safely

A useful k6 pipeline should answer two separate questions:

1. **Is this repository change safe and internally consistent?**
2. **Should this automation generate sustained traffic against a real environment?**

Those questions should not be collapsed into one automatic pull-request job.

## Recommended CI split

### Pull requests: deterministic evidence

Use PR CI for bounded, reproducible checks:

- validate k6 configuration and repository contracts;
- build the exact runtime you intend to use;
- run smoke against a repository-owned local fixture;
- inspect sustained profiles without executing them;
- validate thresholds, target policy, and summary schema;
- publish machine-readable evidence.

This repository implements that boundary in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) and [`.github/workflows/extended.yml`](../.github/workflows/extended.yml).

### Sustained tests: explicit operator intent

Load, stress, and soak are controlled traffic experiments. They should require:

- known target ownership;
- an approved environment and test window;
- downstream capacity awareness;
- observability and abort criteria;
- explicit target authorization.

Here, the runtime requires `K6_BASE_URL`, `K6_ALLOW_LOAD_TEST=true`, and an exact hostname match in `K6_ALLOWED_HOSTS`.

## Stable CI conclusions

Use stable aggregate jobs as branch-protection signals. This repository exposes:

- `ci-gate` for guardrails + deterministic smoke;
- `extended-gate` for zero-sustained-traffic profile validation;
- `security-gate` for supply-chain and runtime evidence.

A stable gate name lets internal jobs evolve without forcing branch-protection configuration to track every implementation detail.

## Publish evidence, not just a green check

A useful CI run should preserve enough context to explain why it passed:

- run ID;
- target class;
- achieved iteration/request counts;
- failure rate;
- p95;
- check rate;
- business success/failure;
- threshold breaches.

The implementation in [`lib/summary.js`](../lib/summary.js) emits both text and compact JSON. See the [verified summary example](../examples/summary-output/README.md).

## Common failure modes

**Automatically load testing every PR.** This creates environment contention and turns code review into an implicit traffic authorization mechanism.

**Using a public demo target as a fallback.** A missing target should fail closed, not silently redirect traffic elsewhere.

**Treating workflow success as performance evidence.** Preserve the resolved workload, achieved demand, errors, latency, checks, business metrics, and threshold outcomes.

**Mutable CI dependencies.** Pin external actions and validate those pins so the workflow executing tomorrow is attributable to reviewed code.
