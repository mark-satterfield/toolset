---
description: Remove process-residue from a deliverable in place, by meaning
argument-hint: <path-to-file>
---

<!-- residue-lint:ignore-file (this command quotes the residue vocabulary to define it) -->

Apply the judgment of `/memre:scan` to $ARGUMENTS, then edit the file in place.

1. Read the whole file. Load the `canonical-output` skill and judge residue by
   meaning, exactly as `/memre:scan` describes — not by keyword.
2. Before you delete residue that records a real decision, its history, or an open
   action, route it to a durable outlet through `/record-observation` so the record
   survives. Only then remove it from the deliverable. Pure noise (a stray `TODO:`,
   a "why this is better" aside with nothing to preserve) is deleted directly.
3. Remove the unambiguous residue. When you cut a section, sentence, or
   parenthetical, repair the surrounding prose so the result reads whole — never
   leave a dangling heading, orphaned list, or half-sentence.
4. Leave the judgment calls in the file. List them for me with line numbers and a
   one-line reason each, so I decide those myself.

Report what you removed, what you routed to an outlet, and what you left for me.
Change nothing outside $ARGUMENTS.
