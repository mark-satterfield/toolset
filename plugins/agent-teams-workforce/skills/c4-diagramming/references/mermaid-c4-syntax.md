# Mermaid C4 syntax — runnable examples

Mermaid ships experimental support for C4 diagrams. The diagram kind is declared on the
first line: `C4Context`, `C4Container`, `C4Component`, `C4Dynamic`, or `C4Deployment`.
This file is the canonical place for fenced Mermaid examples in this skill — copy a block,
rename the elements, and adjust relationships.

## Element vocabulary (shared across all C4 kinds)

- `Person(alias, "Label", "Optional description")` — an internal person/actor.
- `Person_Ext(alias, "Label", "Description")` — an external person.
- `System(alias, "Label", "Description")` — your software system (Level 1 focus).
- `System_Ext(alias, "Label", "Description")` — an external software system.
- `SystemDb(alias, ...)`, `SystemQueue(alias, ...)` — system shaped as a datastore / queue.
- `Container(alias, "Label", "Technology", "Description")` — a deployable/runnable unit.
- `ContainerDb(alias, "Label", "Technology", "Description")` — a container that is a datastore.
- `ContainerQueue(alias, ...)` — a container that is a message queue.
- `Component(alias, "Label", "Technology", "Description")` — a component inside a container.
- `ComponentDb(...)`, `ComponentQueue(...)` — datastore/queue-shaped components.
- Boundaries: `Enterprise_Boundary(alias, "Label") { ... }`,
  `System_Boundary(alias, "Label") { ... }`,
  `Container_Boundary(alias, "Label") { ... }`.
- Relationships: `Rel(from, to, "Label", "Optional technology/protocol")`. Directional
  variants control layout: `Rel_U`/`Rel_Up`, `Rel_D`/`Rel_Down`, `Rel_L`/`Rel_Left`,
  `Rel_R`/`Rel_Right`, plus `BiRel` for bidirectional.
- Layout tuning: `UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")` and
  per-element `UpdateElementStyle(alias, $bgColor="...", ...)`.

---

## Level 1 — System Context (`C4Context`)

An internet banking system used by a personal customer, which sends email and authorizes
payments through external systems.

```mermaid
C4Context
    title System Context diagram for Internet Banking System

    Person(customer, "Personal Banking Customer", "A customer of the bank with personal accounts.")

    System_Boundary(b1, "Internet Banking") {
        System(banking, "Internet Banking System", "Lets customers view accounts and make payments.")
    }

    System_Ext(mainframe, "Mainframe Banking System", "Stores core banking information about accounts and transactions.")
    System_Ext(email, "E-mail System", "The internal Microsoft Exchange e-mail system.")

    Rel(customer, banking, "Views accounts and makes payments using")
    Rel(banking, mainframe, "Gets account information from, and makes payments using", "XML/HTTPS")
    Rel(banking, email, "Sends e-mail using", "SMTP")
    Rel(email, customer, "Sends e-mails to")

    UpdateRelStyle(customer, banking, $offsetY="-40")
    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

---

## Level 2 — Container (`C4Container`)

Zooming into the Internet Banking System to show its deployable/runnable containers.

```mermaid
C4Container
    title Container diagram for Internet Banking System

    Person(customer, "Personal Banking Customer", "A customer of the bank.")

    System_Boundary(c1, "Internet Banking") {
        Container(spa, "Single-Page App", "JavaScript, React", "Delivers the internet banking functionality to the customer's browser.")
        Container(mobile, "Mobile App", "Kotlin / Swift", "Provides a subset of the banking functionality on a smartphone.")
        Container(web, "Web Application", "Java, Spring MVC", "Delivers the static content and the single-page app.")
        Container(api, "API Application", "Java, Spring Boot", "Provides banking functionality via a JSON/HTTPS API.")
        ContainerDb(db, "Database", "PostgreSQL", "Stores user registration, hashed credentials, access logs, etc.")
    }

    System_Ext(email, "E-mail System", "The internal Microsoft Exchange system.")
    System_Ext(mainframe, "Mainframe Banking System", "Stores core banking information.")

    Rel(customer, web, "Visits bigbank.com using", "HTTPS")
    Rel(customer, spa, "Views accounts and makes payments using")
    Rel(customer, mobile, "Views accounts and makes payments using")

    Rel(web, spa, "Delivers to the customer's browser")
    Rel(spa, api, "Makes API calls to", "JSON/HTTPS")
    Rel(mobile, api, "Makes API calls to", "JSON/HTTPS")
    Rel_Back(api, db, "Reads from and writes to", "JDBC")
    Rel(api, email, "Sends e-mail using", "SMTP")
    Rel(api, mainframe, "Makes API calls to", "XML/HTTPS")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

---

## Level 3 — Component (`C4Component`)

Zooming into a single container — the API Application — to show its components.

```mermaid
C4Component
    title Component diagram for Internet Banking System - API Application

    Container(spa, "Single-Page App", "JavaScript, React", "Banking UI in the browser.")
    Container(mobile, "Mobile App", "Kotlin / Swift", "Banking UI on a phone.")
    ContainerDb(db, "Database", "PostgreSQL", "Stores users, hashed credentials, access logs.")
    System_Ext(mainframe, "Mainframe Banking System", "Core banking records.")

    Container_Boundary(api, "API Application") {
        Component(signin, "Sign In Controller", "Spring MVC REST Controller", "Allows users to sign in.")
        Component(accounts, "Accounts Summary Controller", "Spring MVC REST Controller", "Provides account balances.")
        Component(security, "Security Component", "Spring Bean", "Provides authentication and authorization.")
        Component(mainframeFacade, "Mainframe Banking Facade", "Spring Bean", "Talks to the mainframe.")

        Rel(signin, security, "Uses")
        Rel(accounts, mainframeFacade, "Uses")
        Rel(security, db, "Reads from and writes to", "JDBC")
        Rel(mainframeFacade, mainframe, "Makes API calls to", "XML/HTTPS")
    }

    Rel(spa, signin, "Makes API calls to", "JSON/HTTPS")
    Rel(spa, accounts, "Makes API calls to", "JSON/HTTPS")
    Rel(mobile, signin, "Makes API calls to", "JSON/HTTPS")
    Rel(mobile, accounts, "Makes API calls to", "JSON/HTTPS")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

---

## Deployment view (`C4Deployment`) — optional, for arc42 section 7

Maps containers onto the infrastructure nodes that run them.

```mermaid
C4Deployment
    title Deployment diagram for Internet Banking System - Live

    Deployment_Node(mobile, "Customer's mobile device", "Apple iOS / Android") {
        Container(mobileApp, "Mobile App", "Kotlin / Swift")
    }
    Deployment_Node(browser, "Customer's computer", "Microsoft Windows / Apple macOS") {
        Deployment_Node(chrome, "Web Browser", "Chrome, Firefox, Safari, or Edge") {
            Container(spa, "Single-Page App", "JavaScript, React")
        }
    }
    Deployment_Node(aws, "Big Bank plc", "Amazon Web Services, eu-west-1") {
        Deployment_Node(k8s, "Live Kubernetes Cluster", "EKS") {
            Container(api, "API Application", "Java, Spring Boot", "x3 replicas")
        }
        Deployment_Node(rds, "Managed Database", "Amazon RDS") {
            ContainerDb(db, "Database", "PostgreSQL")
        }
    }

    Rel(spa, api, "Makes API calls to", "JSON/HTTPS")
    Rel(mobileApp, api, "Makes API calls to", "JSON/HTTPS")
    Rel(api, db, "Reads from and writes to", "JDBC")

    UpdateLayoutConfig($c4ShapeInRow="2", $c4BoundaryInRow="1")
```

---

## Authoring notes

- The first non-blank line **must** be the diagram kind (`C4Context`, etc.); no leading
  whitespace before it.
- `title` is optional but recommended — it becomes the diagram caption.
- Define elements first, then relationships. Forward references in `Rel(...)` to an
  element defined later in the same block are tolerated, but defining first reads better.
- Layout for the C4 kinds is auto-managed. Do not fight it with manual coordinates; steer
  with `UpdateLayoutConfig`, the directional `Rel_U/D/L/R` variants, and `UpdateRelStyle`
  offsets instead.
- Keep each diagram to one C4 level. If a diagram needs both containers and their internal
  components to make sense, split it into a Container diagram plus one Component diagram.
