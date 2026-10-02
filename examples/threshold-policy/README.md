# k6 thresholds and SLO policy example

Central threshold construction lives in [`lib/thresholds.js`](../../lib/thresholds.js). Profiles provide the policy inputs instead of duplicating threshold strings across scripts.

```javascript
thresholds: sloThresholds({
  checksRate: 0.99,
  errorRate: config.errorRate,
  p95Ms: config.p95Ms,
})
```

The shared policy can gate:

- check pass rate;
- HTTP failure rate;
- p95 HTTP duration;
- business success/failure rates;
- dropped iterations for sustained arrival-rate profiles.

Thresholds are exit criteria. Checks are per-observation assertions. A scenario can have passing checks and still fail an aggregate latency/error threshold, or vice versa. See [the thresholds vs checks guide](../../docs/K6-THRESHOLDS-AND-CHECKS.md).
