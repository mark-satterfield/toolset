# Update playbook — integration and correction

The effective version (`arc42/`) changes in two ways: by integrating an approved target, and by
correcting it from what was built. Both follow the same loop: list the changed elements, find every
view that shows them, update or delete each view, check the invariants, report.

```text
   changed elements (from the delta, or from built/)
                 |
                 v
   find every effective view that shows each one     catalog: subject / shows,
   (every scope: system, domain, service, component)  in arc42/
                 |
                 v
   replace, update or delete each view;               named for its subject,
   add the target's new views                         in the section the MODEL names
                 |
                 v
   check the invariants (consistency-rules.md)
                 |
                 v
   report: changed elements, views changed, invariant check, not integrated
```

## Integration of an approved target

Inputs: `target/<subject>/` (the target views), `target/<subject>/delta/` (what changes), and the
effective views the catalog returns for every element the delta names.

1. **List the changed elements from the delta.** Every element added, changed or removed.
2. **Find the effective views.** For each element, every view in `arc42/` whose `subject` or `shows`
   names it. Compare that list with the target: every effective view showing a changed element needs
   a target view, an in-place update, or a deletion. An effective view the target did not account for
   is reported under "Not integrated" rather than left contradicting the target.
3. **Apply each target view.**
   - A target view that corresponds to an effective view replaces it in place: same path, the
     target's content.
   - A target view for a new subject is added in the section folder the MODEL's view table names,
     named for its subject.
   - An effective view whose subject the change removes is deleted, and every link to it is updated.
   - An effective view that shows a changed element among others is updated in place: the element's
     box, relationships and prose change; the rest stays.
4. **Section 4 and section 8.** When the target carries its own copy of the strategy or of a concept,
   the effective file is replaced with it. Otherwise they are left as they are.
5. **Section 2 is not written.** A target that would change a constraint is reported, not applied.

The target folder stays in place after integration: later phases read the delta from it, and the
caller removes it once the Specs and Tasks made from it are written.

## Correction from built

Inputs: `built/<subject>/` (each view records a difference between what was built and the effective
version, citing the code) and the effective views that show the elements it names.

1. **List the elements the built views differ on.**
2. **Find every effective view that shows each one**, at every scope.
3. **Correct each view** to describe what was built, the same way as an integration: replace, update
   in place, add or delete.
4. **Report each built view the effective version now matches**, so the caller removes it. A built
   view is kept only for a difference the effective version has not been brought up to date with.

## Worked example A — integrating a new service

The approved target `target/notification-preferences/` adds a preferences service with one table,
publishing one event that an existing settings service consumes.

1. Changed elements: the preferences service (added), its table (added), the event (added), the
   settings service (changed: it consumes the event).
2. Effective views found: the system container view (`05-building-block-view/README.md`), the
   domain view of the settings service's domain, the settings service's component view and its
   sequence for saving settings, the system event flow in `06-runtime-view/`, the system deployment
   in `07-deployment-view/README.md`.
3. Applied: the system container, domain, event flow and deployment views are replaced with the
   target's versions, which show the new service; the settings service's component and sequence views
   are updated in place to show the consumer; the new service's component, data model, sequence and
   stack views are added under its subject folder in sections 5, 6 and 7.
4. Invariants: the new service appears at system, domain and service scope; every `shows` list names
   it where the diagram shows it; no view still shows the settings service without the consumer.

## Worked example B — correcting from built

`built/settings-service/` records that the built table uses a different sort key than the effective
data model shows.

1. Changed element: the settings table.
2. Effective views found: the settings service's physical data model and the sequence diagrams that
   query the table.
3. Corrected: the data model shows the built key; the sequences show the query the code runs.
4. Reported: `built/settings-service/` now matches the effective version and can be removed.
