# CDS Elements — Schema 1.x → 2.0 Migration Notes

Canonical record of the customizable-design-elements schema **2.0.0** change and
how to migrate a live 1.x data file. Machinery only — libraries, rules, skills,
and reference docs are out of scope here.

Reference: the schema itself (`validation/customizable-design-elements.schema.json`)
and the migration tooling (`tools/migrate-elements.py`, `tools/check-values-parity.py`).

---

## 1. What changed (1.x → 2.0)

| # | Change | Closes |
|---|--------|--------|
| 1 | **`dark: mirror` sentinel.** A theme's `dark` mode may be the literal string `mirror`, meaning "the dark bindings are identical to this theme's light bindings." Replaces the ~500-line convention of a fully commented-out duplicate dark block per non-flipping theme. | finding 27 |
| 2 | **`geometry.elements` group.** A new fixed-element-width scale, emitted `--element-{key}`. `conversion-card` (448px) moves here, out of `geometry.containers`. The `containers:` invariant ("width ≥ page width") is now true without exception. | ruling 6, finding 23 |
| 3 | **Color-mode universes declared.** The schema documents that binding modes are `light | dark` only, and that the runtime `system` mode resolves at load time to one of the two and is never stored in data. The mode enum is unchanged. | finding 34 |
| 4 | **`$conventions.role` corrected.** The role emission truth is the bare `--{role key}` (the dead `--role-{role key}` form is retired). | finding 25, enhancement #4 |
| 5 | **Contrast bug corrected in the seed.** Light-mode tile inks that were near-black over dark panels grounds are rebound to ivory (see §3). | finding 26 |

Findings 33 (YAML naming/data hygiene) are not part of this schema change; they
remain data-side cleanups tracked separately.

### Generator contract for `dark: mirror`

`mirror` is a **full copy**, not a partial override: the generator emits the
theme's light bindings again for dark mode. It is only meaningful on the `dark`
mode, and only where a concrete `light` mode exists to mirror. Omitting `dark`
entirely still parses as "no dark divergence"; `dark: mirror` states that intent
explicitly and machine-readably (and is visible to the semantic hash, where a
comment block was not).

### `--container-conversion-card` compatibility alias

Until consumers migrate off the old container-scale name, the generator emits
`--container-conversion-card` as an **alias** of `--element-conversion-card`.
Both resolve to the same 448px value. New code should consume
`--element-conversion-card`.

---

## 2. The `conversion-card` move

Before (schema 1.x):

```yaml
geometry:
  containers:
    marketing-primary: { value: "1440px", ... }
    editorial:         { value: "1400px", ... }
    conversion-card:   { value: "448px",  ... }   # a card, not a wrapper
```

After (schema 2.0):

```yaml
geometry:
  containers:
    marketing-primary: { value: "1440px", ... }
    editorial:         { value: "1400px", ... }
  elements:
    conversion-card:   { value: "448px",  ... }    # --element-conversion-card
```

The value (448px) is unchanged. Emission moves from `--container-conversion-card`
to `--element-conversion-card`, with the former kept as an alias (above).

---

## 3. Contrast-bug rebindings (finding 26)

In the **light** modes of `clarity`, `default`, `punctuation`, and `statement`,
tile inks 1 and 2 were bound to near-black ink over dark panels grounds — dark
ink on a dark ground. Each theme's **dark** mode already binds ivory inks over
the same grounds; the light modes are brought into line.

Grounds and inks resolve as: `panels-a` → stronger-indigo `#2B3A6B`; `panels-g`
→ stronger-slate `#3D4A6B`; `text-ink` → neutral-950 `#141413`; `text-ivory` →
neutral-050 `#FAF9F5`.

| Theme | Mode | Role | Ground | Old ink | New ink |
|-------|------|------|--------|---------|---------|
| clarity | light | tile-ink-1 | panels-a `#2B3A6B` | `--color-text-ink` `#141413` | `--color-text-ivory` `#FAF9F5` |
| clarity | light | tile-ink-2 | panels-g `#3D4A6B` | `--color-text-ink` `#141413` | `--color-text-ivory` `#FAF9F5` |
| default | light | tile-ink-1 | panels-a `#2B3A6B` | `--color-text-ink` `#141413` | `--color-text-ivory` `#FAF9F5` |
| default | light | tile-ink-2 | panels-g `#3D4A6B` | `--color-text-ink` `#141413` | `--color-text-ivory` `#FAF9F5` |
| punctuation | light | tile-ink-1 | panels-a `#2B3A6B` | `--color-text-ink` `#141413` | `--color-text-ivory` `#FAF9F5` |
| punctuation | light | tile-ink-2 | panels-g `#3D4A6B` | `--color-text-ink` `#141413` | `--color-text-ivory` `#FAF9F5` |
| statement | light | tile-ink-1 | panels-a `#2B3A6B` | `--color-text-ink` `#141413` | `--color-text-ivory` `#FAF9F5` |
| statement | light | tile-ink-2 | panels-g `#3D4A6B` | `--color-text-ink` `#141413` | `--color-text-ivory` `#FAF9F5` |

`tile-ink-3` (over `panels-d` = stronger-umber `#7A4A28`) and `tile-ink-accent`
were already ivory and are unchanged. Themes `feature-dark`, `code`, and `deep`
are inherently dark and already bind ivory inks; unchanged.

For `punctuation` and `statement`, whose dark mode is now `dark: mirror`, the
fix propagates automatically — mirror copies the corrected light bindings.

This is a **value correction**, not a mechanical rewrite: `migrate-elements.py`
detects these pairs and warns, but does not apply the fix.

---

## 4. The `dark: mirror` conversion (seed)

Five themes did not change on mode flip and carried a full commented-out dark
block: `punctuation`, `statement`, `feature-dark`, `code`, `deep`. Each block is
replaced with:

```yaml
    modes:
      light:
        bindings: { ... }
      dark: mirror
```

`clarity` and `default` genuinely diverge on mode flip and keep both concrete
`light` and `dark` blocks. `editorial` is an alias of `default` and declares no
modes.

---

## 5. Migrating a live 1.x file

`tools/migrate-elements.py` applies only the unambiguously mechanical transforms,
**preserving comments and formatting**:

1. `$schema_version` → `2.0.0`
2. `role_var_pattern`: `--role-{role key}` → `--{role key}` (if present)
3. `conversion-card`: `geometry.containers` → `geometry.elements` (if present)

It deliberately does **not** invent `dark: mirror` (comments are not
machine-readable intent) and does **not** apply the contrast fix (a design
decision). It reports, on stderr:

- every concrete theme parsing with no `dark` binding — candidates for
  `dark: mirror`;
- every detected contrast-bug pair (§3) — to be rebound by hand.

```bash
# Dry run (prints migrated YAML to stdout, report to stderr):
python3 tools/migrate-elements.py <elements.yaml> --dry-run

# In place (writes <elements.yaml>, backs up to <elements.yaml>.bak):
python3 tools/migrate-elements.py <elements.yaml> --in-place

# To a new file:
python3 tools/migrate-elements.py <elements.yaml> --out <dest.yaml>
```

### The live SkillSpoke YAML

The live file is
`/Users/msat1971/projects/SkillSpoke/app/SkillSpoke/.customizable-design-elements.yaml`.

**Do not migrate it now.** The cutover is a separate, human-gated step. When it
happens, the one-command mechanical pass is:

```bash
python3 tools/migrate-elements.py \
  /Users/msat1971/projects/SkillSpoke/app/SkillSpoke/.customizable-design-elements.yaml \
  --in-place
```

Then, by hand (the migrator's report names exactly where):

1. Replace each commented-out mirror dark block with `dark: mirror` for the
   themes the report lists as having no `dark` binding.
2. Apply the §3 contrast rebindings in the light modes the report flags.

Notes specific to the SkillSpoke file: it carries no `geometry:` block, so the
`conversion-card` move is a no-op there; it still declares the dead
`--role-{role key}` (finding 25), which the migrator corrects.

Validate the result:

```bash
python3 validation/lint-elements.py <migrated.yaml>
```

The linter accepts schema 2.x only and rejects a 1.x file with a pointer to this
migrator.
