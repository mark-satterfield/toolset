---
name: load-testing
description: How to write load tests and performance benchmarks whose pass or fail is a numeric budget taken from the non-functional requirements — choosing the test type (smoke, load, stress, spike, soak), modelling load as an arrival rate or as concurrent users, expressing budgets as percentile thresholds that set the exit code (k6 thresholds, Locust exit code on quitting), warm-up and sample size, recording the measurement context, and what changes for serverless targets (Lambda concurrency and cold starts, API Gateway throttling, downstream quotas). Use when writing, reviewing or running a load test, a benchmark or a resilience probe.
user-invocable: false
---

# Load testing and performance benchmarks

A load test is a test: it has a budget, it runs, and its exit code says whether the budget held.
A run that prints numbers and always exits 0 is a measurement, not a test.

## 1. Every budget comes from a requirement

- Each threshold traces to a non-functional requirement (TRD, spec or acceptance criterion): the
  metric, the percentile, the limit and the load level it applies at. Record the trace beside the
  threshold (a comment or a budget table).
- A requirement with no number, no percentile or no load level cannot be benchmarked. Report it as
  a gap; never invent a "reasonable" number.
- Measure what the requirement states: a p95 requirement is asserted on p95, never on the average.
  Assert the error rate as well as latency: a fast run that fails 5% of requests did not meet the
  budget.

## 2. Choose the test type for the question

| Type | Question it answers | Shape |
| --- | --- | --- |
| Smoke | Does the script and target work at all? | 1–2 virtual users, seconds |
| Load | Does the budget hold at the expected load? | ramp to the stated load, hold it |
| Stress | Where does it break, and how? | ramp beyond the stated load in steps |
| Spike | Does it absorb a sudden burst and recover? | jump to a multiple of the load, drop back |
| Soak | Does it degrade over time (leaks, connection exhaustion)? | the stated load for a long period |

Run a smoke test before any other type. A benchmark that gates a build is normally a load test at
the level the requirement names.

## 3. Model the load the requirement describes

- **Open model (arrival rate)** — requests per second regardless of how slow the system is. Use it
  when the requirement is a throughput ("200 requests per second"): k6 `constant-arrival-rate` or
  `ramping-arrival-rate` (with `preAllocatedVUs` and `maxVUs`), Locust `constant_throughput`.
  Arrival-rate executors pace iterations themselves: do not add `sleep()`.
- **Closed model (concurrent users)** — a fixed number of users, each waiting for its response.
  Use it when the requirement is a number of simultaneous users: k6 `constant-vus` or
  `ramping-vus`, Locust `--users` with `--spawn-rate` and a `wait_time` (`between`, `constant`).
  A closed model under-reports latency when the system slows (users wait instead of arriving).
- Exclude warm-up from the measured window (a separate scenario with `startTime`, or tag the
  warm-up and set thresholds on the measured tag only). State the sample size; a percentile from a
  few dozen requests is noise.

## 4. Make the budget set the exit code

k6 (JavaScript): thresholds in `options` fail the run and set a non-zero exit code.

```javascript
export const options = {
  scenarios: {
    steady: { executor: 'constant-arrival-rate', rate: 50, timeUnit: '1s', duration: '2m', preAllocatedVUs: 50, maxVUs: 100 },
  },
  thresholds: {
    http_req_failed: [{ threshold: 'rate<0.01', abortOnFail: true }], // NFR-PERF-2: < 1% errors
    http_req_duration: ['p(95)<200', 'p(99)<500'],                    // NFR-PERF-1
    checks: ['rate>0.99'],
  },
}
```

Thresholds can target one scenario or tag (`'http_req_duration{scenario:steady}'`); use that to
keep warm-up or setup traffic out of the budget. `check()` records an assertion without failing
the run: pair it with a `checks` threshold.

Locust (Python): set `environment.process_exit_code` in a `quitting` listener and run headless
with a run time.

```python
from locust import events


@events.quitting.add_listener
def _budget(environment, **_kw):
    total = environment.stats.total
    failed = total.fail_ratio > 0.01 or total.get_response_time_percentile(0.95) > 200  # NFR-PERF-1/2
    environment.process_exit_code = 1 if failed else 0
```

`locust --headless --users 100 --spawn-rate 10 --run-time 2m -H <target>`. A custom
`LoadTestShape` gives stages (spike, step stress).

A micro-benchmark of one function in the test suite (for example `pytest-benchmark`, or a timing
assertion over many iterations) follows the same rules: a percentile or statistic from the
requirement, warm-up excluded, iterations stated.

## 5. Red before Green

Before the implementation exists the benchmark fails because the operation is missing (connection
refused, 404, import error of the target). That is the intended Red only when the script itself is
valid: run the smoke shape against something that exists (a stub endpoint in the harness, or a
syntax check such as `k6 inspect`) so a script error is never mistaken for Red.

## 6. Record the measurement context

Every result states: the target and environment, the load model and its numbers, duration and
warm-up, sample size, percentiles measured, the tool and version, and where the load generator ran.
A result without its context cannot be compared with the next run.

## 7. Serverless targets

Look up current quotas and behaviour with the AWS documentation tools; the values below are the
documented defaults to check against, not guarantees.

- **Lambda concurrency** — an account has a regional concurrency quota (1,000 by default) shared by
  every function; reserved concurrency caps one function. Over it, synchronous calls fail with
  `TooManyRequestsException` (429) and API Gateway returns 429 or 500. A load test above that level
  measures throttling, not the code. Watch `ConcurrentExecutions` and `Throttles`.
- **API Gateway** — account-level throttling (10,000 requests per second by default, with a burst
  bucket) and any stage or usage-plan limits apply before Lambda.
- **Cold starts** — the first requests on new execution environments are slower. A ramp creates
  cold starts throughout; a budget about steady state excludes the ramp, a budget about first
  response includes it. Say which the requirement means.
- **Downstream quotas** — DynamoDB on-demand scaling, SQS, EventBridge and third-party APIs have
  their own limits; the slowest one sets the ceiling. Payload limits differ per hop.
- **Cost and safety** — load generates real cost and can trip alarms. Run only against the
  environment the caller designates, never against shared or production endpoints, and bound every
  run by duration and rate.
