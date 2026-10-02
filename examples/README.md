# k6 performance testing examples

These examples are discovery-oriented entry points into the production framework. They deliberately reuse the repository's native tests, shared modules, safety checks, Docker runtime, and CI workflows instead of creating parallel example code that can drift from the real implementation.

| Area | Entry point | Primary search intent |
| --- | --- | --- |
| API smoke | [api-smoke](api-smoke/README.md) | k6 API smoke test example |
| Arrival rate | [constant-arrival-rate](constant-arrival-rate/README.md) | k6 arrival rate / load testing example |
| Thresholds | [threshold-policy](threshold-policy/README.md) | k6 thresholds example |
| Business metrics | [custom-business-metrics](custom-business-metrics/README.md) | k6 custom metrics example |
| CI | [github-actions](github-actions/README.md) | k6 GitHub Actions example |
| Docker | [docker](docker/README.md) | k6 Docker example |
| Evidence | [summary-output](summary-output/README.md) | k6 JSON summary / test results |

## Safety boundary

Smoke uses the repository-owned loopback fixture. Sustained load, stress, and soak profiles require an explicit target, `K6_ALLOW_LOAD_TEST=true`, and an exact hostname in `K6_ALLOWED_HOSTS`. Examples do not weaken those controls.
