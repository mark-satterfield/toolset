# OKF concept examples

Cross-domain examples of well-formed concept documents. Copy the shape,
not the data.

---

## Data warehouse table (resource-bound)

```markdown
---
type: BigQuery Table
title: Orders
description: One row per completed customer order across all channels.
resource: https://console.cloud.google.com/bigquery?p=acme&d=sales&t=orders
tags: [sales, orders, revenue]
timestamp: 2026-07-04T12:00:00Z
---

# Schema

| Column        | Type      | Description                                         |
|---------------|-----------|-----------------------------------------------------|
| `order_id`    | STRING    | Globally unique order identifier.                   |
| `customer_id` | STRING    | FK into [customers](/tables/customers.md).          |
| `total_usd`   | NUMERIC   | Order total in US dollars.                           |
| `placed_at`   | TIMESTAMP | When the customer submitted the order.              |

# Joins

Joined with [customers](/tables/customers.md) on `customer_id` and with
[line_items](/tables/line_items.md) on `order_id`.

# Citations

[1] [Orders table schema](https://console.cloud.google.com/bigquery?p=acme&d=sales&t=orders)
```

---

## Metric (abstract, no `resource`)

```markdown
---
type: Metric
title: Monthly Recurring Revenue
description: Sum of all active subscription revenue normalized to monthly.
tags: [revenue, saas]
timestamp: 2026-07-04T12:00:00Z
---

# Monthly Recurring Revenue (MRR)

## Definition

Sum of all active subscriptions normalized to a monthly amount. Excludes
one-time fees and overages.

## Formula

`MRR = Σ(active_subscription_monthly_value)`

## Related

- [Churn Rate](./churn.md) uses MRR as its denominator.
- [ARR](./arr.md) = MRR × 12.
```

---

## API endpoint

```markdown
---
type: API Endpoint
title: Create Order
description: Submit a new order for a customer.
resource: https://api.acme.com/v2/orders
tags: [orders, write]
timestamp: 2026-07-04T12:00:00Z
---

# Request

`POST /v2/orders`

| Field         | Type   | Required | Description                    |
|---------------|--------|----------|--------------------------------|
| `customer_id` | string | yes      | ID of the ordering customer.   |
| `items`       | array  | yes      | Line items; see below.         |

# Examples

```bash
curl -X POST https://api.acme.com/v2/orders \
  -H 'Authorization: Bearer $TOKEN' \
  -d '{"customer_id":"c_123","items":[{"sku":"A1","qty":2}]}'
```

Writes a row to the [orders table](/tables/orders.md).

# Citations

[1] [Orders API reference](https://api.acme.com/docs/orders)
```

---

## Playbook (operational)

```markdown
---
type: Playbook
title: Incident response — data freshness alert
description: Steps to triage a freshness alert on the orders pipeline.
tags: [oncall, incident]
timestamp: 2026-07-04T12:00:00Z
---

# Trigger

A freshness alert fires when [orders](/tables/orders.md) lags more than
30 minutes behind its expected SLA.

# Steps

1. Check the [ingestion job dashboard](https://example.com/dash).
2. Confirm upstream source availability.
3. If the source is healthy, escalate to the data platform on-call.
```

---

## Reference (mirrored external material)

```markdown
---
type: Reference
title: CC BY-SA 4.0 License
description: Creative Commons Attribution-ShareAlike 4.0 license terms.
resource: https://creativecommons.org/licenses/by-sa/4.0/
tags: [license]
timestamp: 2026-07-04T12:00:00Z
---

Mirror of the license under which the source dataset is published, so
concepts can cite [this reference](/references/cc-by-sa-4-0.md) instead
of an external URL that may rot.
```

---

## Root index with version declaration

```markdown
---
okf_version: "0.1"
---

# Acme Sales Knowledge

Curated knowledge about Acme's sales data and operations.

# Contents

* [Datasets](datasets/) - Logical groupings of tables.
* [Tables](tables/) - One concept per warehouse table.
* [Metrics](metrics/) - Business KPIs and their definitions.
* [Playbooks](playbooks/) - Operational procedures.
```
