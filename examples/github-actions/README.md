# k6 GitHub Actions example

The production example is the repository's own [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml).

The pull-request path is intentionally safe:

1. validate workflow/runtime provenance;
2. prove shell and runtime refusal contracts;
3. build the governed Docker runtime;
4. run bounded smoke against `127.0.0.1:4020`;
5. validate the structured summary;
6. publish a human-readable GitHub job summary;
7. upload the bounded evidence artifact;
8. require the aggregate `ci-gate`.

Sustained load, stress, and soak traffic is **not** an automatic PR side effect. The extended workflow resolves those profiles with zero sustained traffic.

See [Running k6 in GitHub Actions](../../docs/K6-GITHUB-ACTIONS.md) for the reasoning behind the gate design.
