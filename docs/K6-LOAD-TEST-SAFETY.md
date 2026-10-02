---
title: Safe k6 Load Testing
description: A defense-in-depth authorization model for preventing accidental performance-test traffic and validating k6 load, stress, and soak profiles with zero sustained traffic.
---

# Safe k6 Load Testing: Preventing Accidental Production Traffic

Performance automation can cause real load. A safe framework should make the target and the operator's authorization explicit rather than relying on naming conventions or good intentions.

## Fail closed on the target

This repository has no public/demo fallback. Every traffic-capable invocation requires an explicit `K6_BASE_URL`.

Sustained profiles additionally require:

```text
K6_ALLOW_LOAD_TEST=true
K6_ALLOWED_HOSTS=<exact authorized hostname>
```

The target hostname must exactly match the allowlist. Target classification is recorded as evidence but does not itself authorize traffic.

## Enforce policy at more than one layer

The shell wrapper rejects unsafe sustained execution before starting k6. The k6 runtime independently validates the target and authorization. This protects against bypassing the wrapper with a direct `k6 run`.

Defense in depth matters because performance-test commands are often copied into CI jobs, containers, local terminals, and runbooks.

## Validate profiles with zero sustained traffic

Use `k6 inspect --include-system-env-vars` to resolve scenarios and thresholds without running the sustained workload:

```bash
K6_BASE_URL=https://example.invalid \
K6_ALLOW_LOAD_TEST=true \
K6_ALLOWED_HOSTS=example.invalid \
k6 inspect --include-system-env-vars tests/load.js
```

This makes configuration review cheap and safe. It is particularly useful on pull requests.

## Authorization is not operational readiness

Exact-host authorization reduces accidental targeting risk; it does not prove that a test should run now. Operators still own:

- environment ownership;
- change control and test windows;
- test-data safety;
- downstream dependencies;
- capacity expectations;
- abort criteria;
- incident response;
- monitoring and generator health.

## Preserve attribution

Each run should make it possible to answer: what target was tested, what demand was requested and achieved, what thresholds applied, what failed, and which runtime executed the experiment. That is why the framework treats the summary and target class as evidence rather than console decoration.
