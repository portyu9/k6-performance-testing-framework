# k6 Performance Testing Framework

**Production-grade Grafana k6 performance testing framework for smoke, load, stress, and soak testing.**

**Safe by default. Evidence by design.** Explicit workloads · centralized thresholds · business metrics · exact-host safety · GitHub Actions · Docker · machine-readable evidence

**[Use this template](https://github.com/portyu9/k6-performance-testing-framework/generate)** · [Quick start](#quick-start) · [Verified evidence](#verified-evidence) · [Examples](#examples) · [Architecture](#architecture) · [Documentation](#documentation)

[![CI](https://github.com/portyu9/k6-performance-testing-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/portyu9/k6-performance-testing-framework/actions/workflows/ci.yml)
[![Extended](https://github.com/portyu9/k6-performance-testing-framework/actions/workflows/extended.yml/badge.svg)](https://github.com/portyu9/k6-performance-testing-framework/actions/workflows/extended.yml)
[![Security](https://github.com/portyu9/k6-performance-testing-framework/actions/workflows/security.yml/badge.svg)](https://github.com/portyu9/k6-performance-testing-framework/actions/workflows/security.yml)
[![Docs](https://github.com/portyu9/k6-performance-testing-framework/actions/workflows/docs.yml/badge.svg)](https://github.com/portyu9/k6-performance-testing-framework/actions/workflows/docs.yml)

[![k6](https://img.shields.io/badge/k6-performance-7D64FF?logo=k6&logoColor=white)](https://k6.io/)
[![JavaScript](https://img.shields.io/badge/JavaScript-scripting-F7DF1E?logo=javascript&logoColor=black)](https://grafana.com/docs/k6/latest/using-k6/javascript-api/)
[![Bash](https://img.shields.io/badge/Bash-guardrails-4EAA25?logo=gnubash&logoColor=white)](https://www.gnu.org/software/bash/)
[![Docker](https://img.shields.io/badge/Docker-runtime-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-CI-2088FF?logo=githubactions&logoColor=white)](https://github.com/features/actions)
[![Trivy](https://img.shields.io/badge/Trivy-security-1904DA?logo=trivy&logoColor=white)](https://trivy.dev/)
[![License](https://img.shields.io/badge/License-MIT-2EA44F?logo=opensourceinitiative&logoColor=white)](LICENSE)
[![Security Policy](https://img.shields.io/badge/Security-Policy-24292F?logo=github&logoColor=white)](.github/SECURITY.md)

> [!CAUTION]
> `load`, `stress`, and `soak` are controlled traffic experiments—not ordinary automated tests. Routine CI performs bounded loopback smoke and zero-traffic profile inspection; sustained traffic requires explicit target ownership, opt-in, and exact-host authorization.

## Verified evidence

The repository does not rely on a marketing-only example. A successful CI smoke run against the repository-owned loopback fixture produced this machine-readable headline on **2026-09-16**:

```text
runId=gha-35061470863-1
target=127.0.0.1
targetClass=local-fixture
iterations=3
requests=5
failedRate=0
p95Ms=1.1928151999999999
checksRate=1
businessAttempts=5
businessSuccessRate=1
businessFailureRate=0
businessP95Ms=1.1928151999999999
thresholdBreaches=0
```

That run completed the `guardrails`, `smoke`, and aggregate `ci-gate` jobs successfully. The numbers above are evidence from that bounded local-fixture run, **not a benchmark claim for another service or environment**.

**Proof:** [GitHub Actions run 35061470863](https://github.com/portyu9/k6-performance-testing-framework/actions/runs/35061470863) · [summary example](examples/summary-output/example-summary.json) · [evidence guide](examples/summary-output/README.md)

## Examples

The examples are intentionally thin: they teach the native k6 and repository contracts without creating a second framework DSL or bypassing the target-authorization model.

| Example | What it demonstrates |
| --- | --- |
| [API smoke](examples/api-smoke/README.md) | Deterministic API smoke execution against the repository-owned fixture |
| [Constant / arrival-rate workloads](examples/constant-arrival-rate/README.md) | Arrival-rate semantics, VU capacity, dropped-iteration interpretation |
| [Threshold policy](examples/threshold-policy/README.md) | Centralized checks, error-rate, latency, and business thresholds |
| [Custom business metrics](examples/custom-business-metrics/README.md) | Stable low-cardinality domain attempts, success/failure, and duration |
| [GitHub Actions](examples/github-actions/README.md) | Safe PR CI, zero-traffic profile inspection, artifacts, and stable gates |
| [Docker](examples/docker/README.md) | Governed runtime build, non-root execution, and safe default startup |
| [Summary output](examples/summary-output/README.md) | Machine-readable evidence and how to interpret it |

For the full map, see [`examples/README.md`](examples/README.md).

## Capabilities

| Plane | Purpose | Traffic behavior | Evidence |
| --- | --- | --- | --- |
| Guardrails | Reject unsafe/missing target or authorization | **Zero traffic** | Shell/runtime contracts + `k6 inspect` |
| Packaged runtime | Prove image identity/startup safety | **Zero traffic** | Built image + `k6 version` |
| Smoke | Prove request/check/metric/summary path | Very low loopback volume | Structured summary |
| Extended profiles | Validate load/stress/soak scenario and threshold configuration | **Zero sustained traffic** | Resolved inspect evidence |
| Business metrics | Observe domain attempts/success/failure/duration | Same scenario traffic | Tagged custom metrics |
| Sustained experiments | Evaluate load, degradation, or endurance | Explicit operator execution | k6 metrics + thresholds/context |
| Security | Source, repository, runtime-image, dependency-change risk | No target traffic | CodeQL, Trivy, Dependency Review |
| Documentation | README/workflow/governance contracts | No target traffic | Documentation status |

## Architecture

```mermaid
flowchart LR
    CHANGE[Repository change] --> BUILD[Tracked k6 image]
    CHANGE --> GUARD[Target + authorization guardrails]
    BUILD --> K6[k6 runtime]
    GUARD --> SMOKE[Bounded loopback smoke]
    K6 --> SMOKE
    SMOKE --> METRIC[HTTP · Checks · Business metrics]
    METRIC --> SUMMARY[Target class + summary evidence]

    CHANGE --> INSPECT[load · stress · soak inspect]
    INSPECT --> ZERO[Zero sustained traffic]

    OP[Authorized operator] --> RUN[Explicit sustained experiment]
    RUN --> SUMMARY

    SUMMARY --> GATES[CI / evidence gates]
    ZERO --> GATES
    GATES --> RESULT[Qualified repository change]

    classDef entry fill:#DDF4FF,stroke:#0969DA,color:#24292F,stroke-width:1.5px;
    classDef policy fill:#FBEFFF,stroke:#8250DF,color:#24292F,stroke-width:1.5px;
    classDef runtime fill:#FFF8C5,stroke:#9A6700,color:#24292F,stroke-width:1.5px;
    classDef evidence fill:#DAFBE1,stroke:#1A7F37,color:#24292F,stroke-width:1.5px;
    class CHANGE,OP entry;
    class BUILD,GUARD,INSPECT policy;
    class K6,SMOKE,RUN runtime;
    class METRIC,SUMMARY,ZERO,GATES,RESULT evidence;
    linkStyle default stroke:#57606A,stroke-width:1.4px;
```

k6 remains the native traffic engine; shared modules own configuration, authorization, threshold, client/metric, and evidence policy without creating a second load-test DSL. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the deeper target/runtime/workload boundaries.

## Safety model

Every traffic-capable invocation requires explicit `K6_BASE_URL`. Sustained `load`, `stress`, and `soak` additionally require:

```text
K6_BASE_URL=<explicit target>
AND
K6_ALLOW_LOAD_TEST=true
AND
target hostname is an exact member of K6_ALLOWED_HOSTS
```

Validated loopback hosts are classified as `local-fixture`; other validated hosts are `explicit-target`. **Classification is evidence, not authorization.** The shell wrapper and k6 runtime independently enforce sustained safety so direct `k6 run` cannot bypass the policy.

These controls reduce accidental targeting risk; environment ownership, change control, test windows, data safety, downstream capacity, incident controls, and observability remain operator responsibilities.

## Quick start

```bash
# start deterministic fixture
node scripts/local-api.js

# bounded smoke
K6_BASE_URL=http://127.0.0.1:4020 K6_RUN_ID=local-smoke bash scripts/run_k6.sh smoke

# zero-traffic guardrails
bash scripts/test_guardrails.sh

# packaged runtime starts with k6 version, not traffic
docker build -t qa-k6-runtime -f docker/Dockerfile .
docker run --rm qa-k6-runtime
```

Inspect a sustained profile without executing traffic:

```bash
K6_BASE_URL=https://example.invalid \
K6_ALLOW_LOAD_TEST=true \
K6_ALLOWED_HOSTS=example.invalid \
k6 inspect --include-system-env-vars tests/load.js
```

For runtime variables, workload models, metrics/threshold semantics, evidence interpretation, packaged runtime details, dependencies, and triage, see [`docs/OPERATIONS.md`](docs/OPERATIONS.md).

## Repository map

```text
.
├── .github/
├── docker/
├── docs/
├── examples/
├── lib/
├── scripts/
└── tests/
```

## Engineering contracts

- **No implicit target:** `K6_BASE_URL` is always explicit; public/demo services are never fallbacks.
- **Defense in depth:** shell and runtime independently reject unsafe sustained execution.
- **Routine CI safety:** pull-request workflows do not automatically run load/stress/soak traffic.
- **Deterministic smoke:** required smoke targets repository-owned `127.0.0.1:4020` at very low volume.
- **Workload clarity:** arrival rate, VU capacity, thresholds, checks, business metrics, and dropped iterations remain distinct concepts.
- **Central threshold policy:** common SLO expressions live in `lib/thresholds.js`; profile changes are deliberate.
- **Low-cardinality observability:** endpoint/scenario tags remain stable and explicit.
- **Contextual interpretation:** p95/threshold results are read with achieved demand, failures, checks, and generator health.
- **Safe image startup:** starting the project image without an explicit scenario runs `k6 version`, generating zero traffic.

## Packaged runtime provenance

[`docker/Dockerfile`](docker/Dockerfile) is the single tracked runtime source. The executing k6 binary is rebuilt from reviewed source identity and the governed security override modules `golang.org/x/crypto` and `google.golang.org/grpc`; their mutable versions live only in `docker/security-overrides/go.mod`, so Dependabot can update them without creating stale documentation.

The final runtime is pinned to Alpine 3.24.2 by digest and performs no package-repository mutation: **final-stage package installation is forbidden**, and broad `apk update` / `apk upgrade` operations are forbidden. The statically built k6 binary uses the CA trust bundle copied from the digest-pinned builder, and the image runs as numeric non-root user `12345`.

The built image is **not claimed to be bit-for-bit reproducible from the Git commit alone** because external source/package retrieval and build-tool behavior remain inputs. Built-image Trivy evidence attests the OS and Go-binary package state actually produced by the governed build.

Runtime-marker updates are eligible for autonomous qualification only after the trusted dependency controller synchronizes explicit source version/commit provenance and the repaired exact head passes runtime, smoke, extended, security, and docs gates.

## Stable CI conclusions

| Stable status | Responsibility |
| --- | --- |
| `ci-gate` | Zero-traffic guardrails, runtime startup/identity, bounded local smoke, semantic summary evidence |
| `extended-gate` | Load/stress/soak `inspect` contracts with **zero sustained traffic** |
| `security-gate` | Supply-chain provenance, CodeQL, repository Trivy, built-image Trivy, Dependency Review when available |

The docs workflow exposes `static-contracts`. Workflow definitions: [`ci.yml`](.github/workflows/ci.yml) · [`extended.yml`](.github/workflows/extended.yml) · [`security.yml`](.github/workflows/security.yml) · [`docs.yml`](.github/workflows/docs.yml).

## Documentation

| Guide | Use it for |
| --- | --- |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Target/configuration, authorization, fixture, runtime, workload, client/metric, evidence boundaries |
| [`docs/TEST_STRATEGY.md`](docs/TEST_STRATEGY.md) | Gate model, profile semantics, interpretation, exit criteria |
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | Commands, runtime inputs, safety, workload models, metrics, evidence, runtime provenance, dependencies, triage |
| [`docs/K6-GITHUB-ACTIONS.md`](docs/K6-GITHUB-ACTIONS.md) | Safe k6 performance testing in GitHub Actions and CI evidence design |
| [`docs/K6-THRESHOLDS-AND-CHECKS.md`](docs/K6-THRESHOLDS-AND-CHECKS.md) | k6 thresholds vs checks, SLO gates, and interpretation |
| [`docs/K6-LOAD-TEST-SAFETY.md`](docs/K6-LOAD-TEST-SAFETY.md) | Safe load-test authorization, target control, and zero-traffic validation |

The deeper workload, authorization, evidence, and performance-interpretation detail lives in `/docs`; the main README intentionally retains only the architecture diagram above.


## Releases

This project uses semantic versioning for public release checkpoints. Changes accumulate under **Unreleased** in [`CHANGELOG.md`](CHANGELOG.md); the release checklist and evidence requirements live in [`docs/RELEASING.md`](docs/RELEASING.md). Prepared v1.0.0 release notes are tracked in [`docs/releases/v1.0.0.md`](docs/releases/v1.0.0.md) so the GitHub Release can be published from a reviewed main-branch commit rather than from an unmerged feature branch.

## Design principle

A strong performance framework makes the experiment answerable: **what target was authorized/classified, what demand was requested and achieved, what HTTP/business signals reported, what threshold mattered, whether the runtime was controlled, and whether the generator became the bottleneck**.
