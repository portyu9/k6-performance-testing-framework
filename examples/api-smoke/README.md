# k6 API smoke test example

The canonical smoke test is [`tests/smoke.js`](../../tests/smoke.js). It uses one VU, three scenario iterations, setup/teardown health checks, tagged API operations, centralized thresholds, and the repository's structured summary.

## Run locally

Terminal 1:

```bash
node scripts/local-api.js
```

Terminal 2:

```bash
K6_BASE_URL=http://127.0.0.1:4020 \
K6_RUN_ID=example-smoke \
bash scripts/run_k6.sh smoke
```

Expected evidence is written to `reports/summary.txt` and `reports/summary.json`.

## Why this example is bounded

The smoke profile targets a deterministic repository-owned fixture and generates only a handful of requests. It proves request/check/metric/summary plumbing; it is not intended to establish capacity or production latency.
