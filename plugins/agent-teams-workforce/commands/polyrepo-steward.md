---
description: Summon the polyrepo-steward — the fleet's caretaker and the place to ask about this project's repositories, which also carries out the fleet's routine management.
argument-hint: "[create|update|delete|deprecate|list|search] [request]"
---

Invoke the **polyrepo-router** skill, handing it everything below as its input:

<request>
$ARGUMENTS
</request>

The router instantiates the polyrepo-steward and relays its reply. The steward answers and
carries out the fleet's routine management; it never authors or edits a repository's content.
