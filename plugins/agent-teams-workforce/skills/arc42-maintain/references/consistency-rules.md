# Consistency rules — invariants across views

These hold across the effective version after every integration and every correction. Each rule
states the invariant, why it holds, how a violation shows, and the repair.

## 1. Every element shown in a view exists in the views of its own subject

**Invariant.** An element that appears in any view (a service in the system container view, a table
in a sequence, a component in a deployment view) also has views of its own at its own scope: a
service has its component and data views, a concept has its file in section 8.

**Why.** A reader who meets an element in one view follows it to its own views for the detail. An
element that exists only as a box in someone else's diagram has no description anywhere.

**Violation signal.** A name in a view's `shows` list that no view names as its `subject`, at any
scope.

**Repair.** Add the element's own views from the target, or report the gap when the target has none.

## 2. No two views contradict each other

**Invariant.** Every view that shows an element shows the same thing about it: the same name, the
same responsibilities, the same relationships, the same data, the same deployment.

**Why.** The same element appears at several scopes. A change applied at one scope and missed at
another leaves two descriptions of one system, and a design that starts from the wrong one is wrong.

**Violation signal.** The system container view shows a service calling another synchronously while
its sequence view shows an event; a data model's key differs from the key a sequence queries; one
view names a component `auth-svc` and another `AuthService` with no glossary entry joining them.

**Repair.** Bring every view that shows the element in line with the approved target or the built
version, at every scope the catalog lists.

## 3. No view contradicts the owner's constraints

**Invariant.** No view describes a design that conflicts with a constraint in section 2.

**Why.** Constraints are the boundary the owner sets for every design.

**Violation signal.** A view shows a technology, an interface style or a cross-service dependency a
constraint excludes.

**Repair.** None by this skill: section 2 is the owner's. Report the conflict with both paths.

## 4. The catalog matches the views

**Invariant.** Every view's `view_type` is a type from the MENU, `scope` is one of system, domain,
service, component or concept, `subject` is the one thing it describes, and `shows` lists every
element in its diagram and no element that is not.

**Why.** Every phase finds views through the catalog. A view whose frontmatter is wrong is a view the
next integration misses.

**Violation signal.** An element in a diagram missing from `shows`; a `shows` entry the diagram does
not contain; a `view_type` the MENU does not list.

**Repair.** Correct the frontmatter to match the view.

## 5. No dangling links

**Invariant.** Every link between views resolves to a file that exists and still covers what the
link says.

**Why.** Views point to their adjacent views at other scopes; a broken link breaks that path.

**Violation signal.** A link to a deleted view, a renamed subject folder, or a heading that no longer
exists.

**Repair.** Update the link to the view that now holds the content, or remove it when the content is
gone.

## 6. Each version describes itself as it is

**Invariant.** No view holds history, a changelog, a decision record, a rule or an open item
(`../../arc42/references/living-document-rules.md`).

**Why.** A reader of any view reads what the design is.

**Violation signal.** "Previously", "we used to", "changed from", "MUST", "TBD", "open question",
"referred to the owner".

**Repair.** Delete it, and restate any current fact it carries as a description of the design.

## Post-pass checklist

- [ ] 1 every element shown has views of its own subject
- [ ] 2 no two views contradict each other, at any scope
- [ ] 3 no view conflicts with a section 2 constraint (conflicts reported, not repaired)
- [ ] 4 catalog frontmatter matches every view touched
- [ ] 5 no dangling links into or out of the views touched
- [ ] 6 no history, rules or open items
