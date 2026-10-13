# Update playbook — decisions and correction

The effective documents (`arc42/`) change in two ways: by writing the solutions architect's
decisions into them, and by correcting them from what a Story built. Both follow the same loop:
take each fact, write it in its one home, replace every restatement with a link, check the
invariants, report.

```text
   facts (from the write request, or from built/<element>/)
                 |
                 v
   write each fact in its home                        the document and heading
   (the form its section requires)                    the request names
                 |
                 v
   find the other documents that describe the         atw-matrix node <entry id>
   same entry; replace a restatement with a link      (its describedBy relationships)
                 |
                 v
   place or update diagrams; keep the catalog true
                 |
                 v
   check the invariants (consistency-rules.md)
                 |
                 v
   report: headings changed and created, links added, restatements removed,
           entries below architecture level, what could not be applied
```

## Writing decisions

Input: a write request. It lists design facts, each with an id, a statement with its reason, one
home (a document path and a heading) and the paths of the documents that must link to it. It may
also list restatements to replace with links, settled disagreements to apply and diagrams to place.

1. **Write each fact in its home**, under the heading named, in the form its section requires:
   - Section 5: what the building block is responsible for, what it owns, its interfaces by name.
     A shared service, component, layer or library states under a heading "Provides" each
     behaviour consumers obtain from it.
   - Section 6: which building blocks interact, in what order, for the scenario and its failures.
     It links to a rule; the rule is stated in its home.
   - Section 7: where it runs and which stack holds each resource.
   - Section 8: the rule as a design fact with its reason.
2. **Replace restatements with links.** In every other document the request names, and in every
   document the matrix lists as describing the same entry (`atw-matrix node <entry id>` names
   each under `describedBy`, with its heading), a restatement of the fact becomes a link to the
   home heading.
3. **Apply settled disagreements.** The statement that stands stays; each statement that lost is
   replaced by a link to it.
4. **Keep the level.** A request entry that is a route path, a field name, a key or index name, a
   parameter name, a metric or alarm name, or a schema is returned as below architecture level,
   unwritten.
5. **Create a document only for a home path that does not exist**, with the catalog front matter
   and a file name that names its subject.
6. **Place and update diagrams.** Place each diagram the request carries under its heading; update
   or redraw a diagram when a fact changes what it shows.
7. **Section 2 is not written.** A fact that conflicts with a constraint is reported and left
   unwritten.

The files changed stay `in-review`; a script sets them to `effective` and commits after review.
A script step runs `atw-matrix sync-documents --paths` on the files changed, so that the matrix
holds each document, its headings and what its `shows` names.

## Correction from built

Input: the documents in `built/<element>/`, each recording a difference between what a Story
built and the effective documents, citing the code; and the effective documents the matrix names
for the elements they differ on.

1. **List the elements the built documents differ on**, and run `atw-matrix node <entry id>` for
   each: `describedBy` names every effective document and heading that describes it.
2. **Take each difference as a fact to correct in its home.** The home is the heading that states
   the fact today.
3. **Correct the home**, then replace any restatement in the other documents that describe the
   element with a link, as for a decision.
4. **Report each built document the effective documents now match**, so that the caller removes
   it. A built document is kept only for a difference the effective documents have not been brought
   up to date with.

A correction from built is made even when it conflicts with a constraint, so that the documents
describe the system as it is. Report the conflict with the correction. The correction records
nothing in the matrix; the next run's `atw-matrix sync-documents` mirrors the corrected documents.

## Worked example A — writing the decisions for a new service

The write request holds four facts: a preferences service is responsible for notification
preferences (home: its section 5 document, heading "Responsibility"); it owns one table (home: the
same document, heading "Owns"); it publishes one event when a preference changes (home: the system
event flow in section 6, heading "Preference changed"); the settings service consumes that event
(home: the settings service's section 5 document, heading "Interfaces"). It names the system
container document as one that must link to the new service.

1. The preferences service's section 5 document does not exist: it is created with catalog front
   matter, named for the service, with the two facts under their headings.
2. The event fact is written under "Preference changed" in the system event flow. The settings
   service's document gains the consumer under "Interfaces".
3. The system container document shows the new service in its diagram and links to its document.
   `atw-matrix node service:settings-service` names, under `describedBy`, the settings service's
   sequence document for saving settings; it
   described the old interaction in its own words, and that sentence becomes a link to "Preference
   changed".
4. Invariants: every `shows` list names the new service where the diagram shows it; each fact is
   stated once; no document contradicts another.

## Worked example B — correcting from built

`built/settings-service/` records that the built service publishes its event through the shared
events service, where the effective documents state that it writes to the event bus itself.

1. Element: the settings service. Fact: how the service publishes its event.
2. Home: the heading that states the publishing path, in the service's section 6 document for
   saving settings.
3. Corrected: the home states that the service publishes through the shared events service. The
   system event flow restated the direct write; that sentence becomes a link to the home heading.
4. Reported: `built/settings-service/` now matches the effective documents and can be removed.
