# Artwork

The artwork contract. Where a page's images, logos, and glyphs come from, how each one is recorded, and the order in which a needed but unsupplied asset is resolved. `foundations/imagery.md` governs how artwork renders — `currentColor` icons, tile aspect ratios, the `srcset` breakpoint ladder — this file governs where artwork comes from and how its provenance is tracked. The composers consult this contract during their asset-discovery step; `package-change` ships the resulting manifest with the bundle.

## Intake

Artwork arrives bound to a slot in the brief: a slot name paired with a file path or a URL — `hero image = ./art/hero.png`, `logo = https://example.com/logo.svg`. A path points at a file already on disk; the composer reads it in place. A URL is fetched into `$CUSTOMIZABLE_DESIGN_SYSTEM_ASSETS_DIR` and the local copy is used from then on.

Every asset carries one entry in the artwork manifest at `<assets-dir>/artwork-manifest.yaml` (the assets directory is `$CUSTOMIZABLE_DESIGN_SYSTEM_ASSETS_DIR`). One entry per slot:

```yaml
# <assets-dir>/artwork-manifest.yaml
assets:
  - slot: hero-image           # the brief slot this asset fills
    file: hero.png             # basename inside the assets directory
    source: url                # path | url
    source_url: https://example.com/hero.png   # the origin when source is url or the located origin for a handoff; empty for a supplied path
    fetched_at: 2026-07-06T14:02:00Z            # ISO-8601 UTC when the file landed in the assets directory; empty until a handoff asset is supplied
    license: free              # declared | free | generated | user-supplied
    status: resolved           # resolved | handoff
    notes: ""                  # locator detail for a handoff, license attribution, or empty
```

- `slot` names the brief slot the asset fills.
- `file` is the asset's basename inside the assets directory.
- `source` is `path` for a supplied on-disk file or `url` for a fetched one.
- `source_url` records the origin for a fetched or located asset; it is empty for a supplied path.
- `fetched_at` is the ISO-8601 UTC instant the file landed in the assets directory.
- `license` is one of `declared` (the brief states the asset's license), `free` (sourced online under a free license floor), `generated` (produced by generation), or `user-supplied` (the user provided the file).
- `status` is `resolved` for an in-hand asset or `handoff` for one located but awaiting the user's retrieval.
- `notes` holds the handoff locator, a license attribution string, or is empty.

## Resolution order

When the brief needs a button glyph, icon, or image for a slot and supplies nothing, the composer resolves the slot in this order and stops at the first step that yields an asset:

1. **System glyph set.** For an icon or button glyph, take it from the system icon-glyph set (`libraries/components/icon-glyphs.md`). These are license-clean and render through `currentColor` per `foundations/imagery.md`.
2. **Generation.** For a raster image, generate it through an available image-generation service; for a glyph, author inline SVG on the icon scale (`foundations/imagery.md`). A generated asset records `license: generated`.
3. **Online sourcing at a free license floor.** Source the asset online only when its license is free; the recorded `license` is `free` and `notes` carries the attribution the license requires. An asset whose license floor is anything above free is not sourced here.
4. **Locate and hand off.** When the right asset exists but is not retrievable by the composer — it sits behind a licensed service the user holds, such as Adobe Creative Cloud — record its exact locator in the manifest with `status: handoff` and `source_url` set to the locator, ask the user to fetch it, and resume with the supplied file. On resumption the entry flips to `status: resolved`, `source: path`, `license: user-supplied`, and `fetched_at` is stamped.
5. **Halt.** When no step yields the asset, halt `ARTWORK_UNRESOLVABLE:{slot}` naming the unresolved slot.

## Rendering

Resolved artwork renders under `foundations/imagery.md`: glyphs paint with `fill="currentColor"` and inherit the surrounding theme; illustration tiles hold their declared aspect ratios; photographic and screenshot assets emit the `srcset` breakpoint ladder. The manifest records provenance; `imagery.md` records presentation.
