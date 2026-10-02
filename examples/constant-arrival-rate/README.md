# k6 arrival-rate load testing example

The canonical load profile is [`tests/load.js`](../../tests/load.js). It uses k6's `ramping-arrival-rate` executor so **requested arrival rate** and **available VU capacity** remain separate concepts.

The profile starts at 2 iterations/second, ramps to 5, then 10, then back to 0. `preAllocatedVUs` and `maxVUs` bound the generator-side capacity.

## Inspect without traffic

Use `k6 inspect` to resolve the workload while sending zero sustained traffic:

```bash
K6_BASE_URL=https://example.invalid \
K6_ALLOW_LOAD_TEST=true \
K6_ALLOWED_HOSTS=example.invalid \
k6 inspect --include-system-env-vars tests/load.js
```

## Run only against an authorized target

```bash
K6_BASE_URL=https://performance.example.internal \
K6_ALLOW_LOAD_TEST=true \
K6_ALLOWED_HOSTS=performance.example.internal \
K6_RUN_ID=authorized-load-001 \
bash scripts/run_k6.sh load
```

Do not treat a configured arrival rate as achieved demand. Interpret it with `dropped_iterations`, errors, checks, latency, and generator health.
