# k6 machine-readable summary example

[`example-summary.json`](example-summary.json) is copied from the headline values emitted by successful GitHub Actions run **35061470863** on 2026-09-16.

The evidence records:

- a run identifier;
- validated target host and target classification;
- iterations and requests;
- HTTP failure rate and p95;
- check pass rate;
- business attempts/success/failure/duration;
- threshold breaches.

The sample is from the repository-owned local fixture. Its latency must not be presented as representative of another environment.

The summary intentionally omits k6's entire raw metric/root-group state. The compact contract is designed for CI decisions, artifacts, dashboards, and later machine processing without pretending that one headline explains the full experiment.
