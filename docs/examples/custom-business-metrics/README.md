---
layout: default
title: k6 custom business metrics example
permalink: /examples/custom-business-metrics/
---

# k6 custom business metrics example

The framework defines business-facing metrics in [`lib/metrics.js`](https://github.com/portyu9/k6-performance-testing-framework/blob/main/lib/metrics.js):

- `business_attempts` — Counter;
- `business_success` — Rate;
- `business_failures` — Rate;
- `business_duration` — time-enabled Trend.

The HTTP client layer records these using stable endpoint/scenario tags. The purpose is to preserve a low-cardinality domain signal beside native k6 HTTP metrics, not to duplicate every HTTP field.

Use business metrics when a request's technical transport result is not enough to answer whether the tested business operation succeeded.
