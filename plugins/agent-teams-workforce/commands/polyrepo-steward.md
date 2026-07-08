---
description: Summon the polyrepo-steward — librarian and caretaker of this project's repositories, their manifest, knowledge, and health.
argument-hint: "[create|update|delete|deprecate|list|search] [request]"
---

Invoke the **polyrepo-router** skill, handing it everything below as its input:

<request>
$ARGUMENTS
</request>

The router instantiates the polyrepo-steward and relays its reply. Do not do the
repository work yourself, and do not read or edit the manifest — that is the steward's
domain.
