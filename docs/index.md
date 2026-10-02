---
layout: default
title: k6 Performance Testing Framework
description: Production-grade Grafana k6 framework for smoke, load, stress, and soak testing with safe-by-default execution and attributable evidence.
permalink: /
---

# k6 Performance Testing Framework

**Safe by default. Evidence by design.**

A production-grade Grafana k6 framework for smoke, load, stress, and soak testing with GitHub Actions, Docker, centralized thresholds, custom business metrics, exact-host safety guardrails, and machine-readable evidence.

## Start

- [Architecture](ARCHITECTURE.md)
- [Operations](OPERATIONS.md)
- [Test strategy](TEST_STRATEGY.md)
- [k6 in GitHub Actions](K6-GITHUB-ACTIONS.md)
- [Thresholds vs checks](K6-THRESHOLDS-AND-CHECKS.md)
- [Safe load testing](K6-LOAD-TEST-SAFETY.md)
- [Examples](../examples/README.md)

## Design position

Routine pull-request CI should prove deterministic behavior without silently authorizing sustained traffic. Load, stress, and soak are controlled experiments; the framework therefore separates configuration validation from explicit operator-authorized execution.

## Evidence model

A useful result answers what target was validated, what workload was requested and achieved, what correctness and business signals reported, what threshold mattered, and whether the generator kept up with demand.

The canonical repository is [portyu9/k6-performance-testing-framework](https://github.com/portyu9/k6-performance-testing-framework).
