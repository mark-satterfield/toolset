# Building Blocks — Entity Catalog

## Entities

| Name | Type | Extends | Construct | Contains | Category | Description |
| --- | --- | --- | --- | --- | --- | --- |
| Archetype | | | Interface | | Marker | An "archetype" is a blueprint or configuration created according to the specification. It is the template from which actual instances are stamped out. |
| DesignElement | | | Abstract | | Base type | The common supertype for anything that can be placed into a layout. Distinct from Element (a raw HTML tag). Leaf members carry a value (their content), unbound in a template and bound when filled. |
| Group | | | Interface | | Marker | A "group" simply bundles multiple DesignElements together. |
| Element | | | Concrete | | Leaf (HTML) | A raw HTML tag: `div`, `span`, `table`, `row`, `button`, `img`. No CDS awareness. Not a DesignElement. |
| Component | Archetype, Group | DesignElement | Concrete | HTML Elements | Entity | A reusable unit of UI built from browser-native building blocks. It encapsulates its own markup, style, and behavior, and defines sizing rules, behavior contracts, accessibility contracts, and token bindings. The smallest unit that carries CDS awareness. It is itself the definition (unrealized); once realized on a page it becomes HTML, CSS, and TypeScript. |
| ComponentLibrary | | | Concrete | A list of Components | Library | An array list of pre-configured Components |
| Shape | Archetype, Group | | Concrete | Components, HTML Elements | Entity | A Shape is primarily a template layout for positioning, and other proportional and geospatial properties of Components and Elements. While CDS may already pre-define most component's with style and other properties. The shape may also provide property values that are not strictly geospatial in nature. |
| ShapeLibrary | | | Concrete | Shapes | Library | An array list of pre-configured Shapes |
| Frame | Archetype, Group | DesignElement | Abstract | Frames, Components, HTML Elements | Base container | A Frame is a container used to group elements together. It is a distinct DesignElement with its own dimensions and properties. The content-bearing unit of page construction: a realized Shape including content, plus a theme. A Frame is assigned a Shape either eagerly (a predefined Shape supplied up front) or lazily (resolved at build time by the Rule Engine from the Section's content). "Deterministic" vs "dynamic" is only when the Shape becomes realized — Rules for some pages are scoped to a type. |
| Page | Archetype | Frame | Concrete | Frames | Entity | The blueprint or configuration of a Page. A page is what ultimately nests inside the vacant space in a ShellDefinition. A page is described in terms of one or more sections (frames). It may be a single section. Many pages are vertical scrolling with sections appearing sequentially. For each shell, there are usually many pages. |
| Section | Archetype | Frame | Concrete | Frames, Components, HTML Elements | Entity | The blueprint or configuration of a Section — a single region of a page. Like any Frame, it is assigned a Shape (eagerly or lazily) and holds its content. A Page is described as one or more Sections in sequence (for example: an editorial hero, a posts crawl, a news index, a call to action). |
| ShellDefinition | Archetype | Frame | Concrete | Sections | Entity | The blueprint or configuration for a shell is the repeating portions of a web site that do not change as pages change. Typically, a shell is composed of a menu, or menus pinned to one or more edges of the canvas, and maybe a common footer or status pinned to the bottom of the canvas, or appended to the bottom of that Page contents. |
| ShapeSelectionRule | | | Concrete | | Rule | For dynamically assigned shapes, a rule tells the generation engine which shape to select or shapes to choose from, or whether a custom shape is necessary. |
| ShapeSelectionRules | | | Concrete | ShapeSelectionRule | Rule set | An array list of ShapeSelectionRules |

## Additional entities

| Name | Type | Extends | Construct | Contains | Category | Description |
| --- | --- | --- | --- | --- | --- | --- |
| DesignToken | | | Concrete | | Config | A design value (color, typography, spacing) consumed by Components via token bindings; feeds CSS generation. |
| DesignTokenLibrary | | | Concrete | DesignTokens | Library | An array list of pre-configured Design Tokens. |
| PageLevelAestheticConstraint | | | Concrete | | Rule | A post-selection validator enforcing coherence across a page (alternating backgrounds, avoiding repeated visual weight). A rejection loop, not a filter. |
| PageLevelAestheticConstraints | | | Concrete | PageLevelAestheticConstraint | Rule set | An array list of PageLevelAestheticConstraint. |
| PageFamily | | | Concrete | | Classifier | The classification a Page carries: landing, app, editorial, docs, or auth. Supplied when a page is composed — stated plainly or obvious from the prompt, otherwise the skill asks. The page family selects the typography and motion register and scopes which PageLevelAestheticConstraints apply. Catalog entries may declare the page family they serve (`shared` = all families). |

## Outputs (generated files)

| Name | Object | Type | Generated from | Description |
| --- | --- | --- | --- | --- |
| CSS | File | CSS | Design Tokens + Shape/Component properties | The stylesheet. |
| Page HTML | File | HTML | Page (its realized Frames), without the shell | The content region on its own. |
| Shell | File | HTML | ShellDefinition | The rationalized html generated from the ShellDefinition and stored for reuse (html?) |
| View | File | HTML | Shell + Page HTML | The view is the combination of the generated Page html inside the Shell. |
