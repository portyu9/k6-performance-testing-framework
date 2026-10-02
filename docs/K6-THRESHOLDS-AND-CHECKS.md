---
title: k6 Thresholds vs Checks
description: How to use k6 checks, thresholds, SLO gates, latency percentiles, error rates, business metrics, and dropped iterations without conflating their meaning.
---

# k6 Thresholds vs Checks: Production Performance Testing

k6 checks and thresholds answer different questions.

## Checks are observations

A check evaluates a condition for an individual execution path or returned value. Typical examples include:

- response/JSON contract is valid;
- returned identifier matches expected setup data;
- execution context matches the intended scenario.

Check results become metrics. A check failure is evidence about an observation; it is not automatically the same thing as violating the experiment's aggregate SLO.

## Thresholds are exit criteria

A threshold evaluates an aggregate metric over the run. This repository centralizes policy in [`lib/thresholds.js`](../lib/thresholds.js):

- `checks`: minimum pass rate;
- `http_req_failed`: maximum HTTP failure rate;
- `http_req_duration`: p95 latency ceiling;
- `business_success` / `business_failures`: domain outcome rates;
- `dropped_iterations`: generator-demand integrity for arrival-rate profiles.

## Why p95 alone is insufficient

A low p95 can coexist with:

- failed requests;
- dropped iterations;
- low check pass rate;
- business failures;
- demand below the requested arrival rate.

Interpret percentile latency together with achieved demand and correctness signals.

## Threshold design rules

1. **Keep common policy centralized.** Profile-specific scripts should provide inputs, not fork the policy implementation.
2. **Separate transport from business success.** An HTTP 200 may still represent a failed business operation.
3. **Gate demand integrity.** For arrival-rate workloads, dropped iterations are evidence that the generator did not keep up with requested demand.
4. **Keep tags low-cardinality.** Thresholds and dashboards remain usable when endpoint/scenario dimensions are stable.
5. **Treat changes as policy changes.** Relaxing a threshold should require the same review discipline as changing the workload.

See [`examples/threshold-policy/README.md`](../examples/threshold-policy/README.md) for the repository implementation.
