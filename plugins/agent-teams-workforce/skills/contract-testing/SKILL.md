---
name: contract-testing
description: How to write and verify consumer-driven contract tests with Pact for REST APIs and for events and messages — consumer tests against a Pact mock provider, matchers that assert type and shape instead of example values, only the fields the consumer uses, one interaction per consumer behaviour including error responses, provider states, provider verification with state handlers, message pacts for asynchronous events, and schema compatibility rules for changing a contract. Use when writing, verifying or reviewing a contract test, or when judging whether a change to an API or event contract breaks a consumer.
user-invocable: false
---

# Consumer-driven contract testing

A contract test proves that one consumer and one provider agree on the interactions the consumer
actually uses. The consumer test records what the consumer sends and needs back (the pact); the
provider verification replays that pact against the real provider. Neither side talks to the other
during its own test.

## 1. What a contract test covers, and what it does not

- Covers: request shape (method, path, query, headers, body), response status, and the response or
  message fields the consumer reads, with their types and formats.
- Does not cover: provider business rules, every field the provider returns, performance, or
  end-to-end flows. Those belong to unit, integration and E2E tests.
- One pact per consumer–provider pair. Name both exactly as the services are named.

## 2. Consumer tests

Pact Python (v3 API, specification V4):

```python
from pathlib import Path
import pytest
from pact import Pact, match


@pytest.fixture
def pact():
    pact = Pact("orders-web", "orders-service").with_specification("V4")
    yield pact
    pact.write_file(Path(__file__).parent / "pacts")


def test_get_order(pact):
    (
        pact
        .upon_receiving("a request for an existing order")
        .given("order exists", id="o-1")
        .with_request("GET", "/orders/o-1")
        .will_respond_with(200)
        .with_body({"id": match.str("o-1"), "total": match.number(12.5)}, content_type="application/json")
    )
    with pact.serve() as srv:
        assert OrdersClient(str(srv.url)).get("o-1").id == "o-1"
```

Pact JS (`@pact-foundation/pact`, `PactV4`) follows the same shape: `addInteraction()`,
`.given()`, `.uponReceiving()`, `.withRequest()`, `.willRespondWith()`, then `executeTest` with the
real client pointed at the mock server.

Rules:

- **Exercise the real consumer code** (the client and the code that reads the response) against the
  mock; a test that only calls the mock with a raw HTTP library proves nothing about the consumer.
- **Match on type and format, not example values** (`like`, `each_like`, `match.int`,
  `match.str`, `regex`, `datetime`). Exact values only where the consumer branches on the value.
- **Only the fields the consumer uses.** Extra fields make the provider unable to change anything.
- **One interaction per consumer behaviour.** Each response variant the consumer handles
  differently (each status value it branches on, 404, 400 validation error, 401/403) gets its own
  interaction; an untested branch is an uncovered contract.
- **Provider states** (`given`) name the data the provider must hold, in domain words, with
  parameters; never encode provider internals.
- Never put real secrets or personal data in a pact; tokens are matched by format.

## 3. Event and message contracts

For asynchronous events the consumer is the handler and the provider is the producer.

```python
pact = Pact("notifications-handler", "orders-service").with_specification("V4")
(
    pact
    .upon_receiving("an order placed event", "Async")
    .given("an order is placed")
    .with_body({"detail-type": match.str("order.placed"), "detail": {"orderId": match.str("o-1")}})
)
pact.verify(handle_event, "Async")  # runs the real handler on the example message
```

Pact JS: `addAsynchronousInteraction().expectsToReceive(...).withJSONContent(...)
.executeTest(handler)`. Assert the envelope fields the consumer reads (event type, version,
correlation fields) as well as the payload. When the project has a standard event envelope, the
contract follows it.

## 4. Provider verification

```python
from pact import Verifier


def state_handler(name, params=None):
    if name == "order exists":
        seed_order(params["id"])


Verifier("orders-service").add_transport(url=base_url).state_handler(state_handler).add_source("./pacts/").verify()
```

- Verify against the provider running from its own code with its dependencies stubbed at the edge,
  never against a shared environment.
- Every provider state the pacts name has a handler; a missing handler is a failing verification,
  not a skip.
- Message providers expose the message the real producing code builds (a message transport such as
  `add_transport(protocol="message", path=...)`); never hand-write the example message.
- Where a broker is used, publish pacts with the consumer version and branch, verify with pending
  and work-in-progress pacts enabled, and gate a release on `can-i-deploy`.

## 5. Red before Green

Before the provider exists, the consumer test passes against the mock (it tests the consumer) and
the provider verification fails (the provider is missing or lacks the behaviour). Red for a contract
writer is the failing verification, or a failing consumer test when the consumer code does not yet
exist. Confirm the failure is the missing behaviour, not a pact file path or harness error.

## 6. Schema compatibility when a contract changes

- Backward compatible for consumers: adding an optional response field, adding an endpoint or an
  event type, widening an accepted request value.
- Breaking: removing or renaming a field a consumer uses, changing a type or format, making an
  optional request field required, changing status codes, changing an event's type name or envelope.
- A breaking change ships as a new version (path, header or event version) alongside the old one
  until every consumer has moved; the pacts show which consumers still use the old one.
- For JSON Schema or OpenAPI, compare the old and new schema of every interaction the pacts record;
  a passing verification of the current pacts is the evidence that no recorded consumer broke.
