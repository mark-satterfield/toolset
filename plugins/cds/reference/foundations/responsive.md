# Responsive Behavior

## §17.1 Breakpoints

| Breakpoint | Width | Layout Behavior |
|---|---:|---|
| Mobile narrow | `< 480px` | Single-column. Section padding drops to 56px top/bottom. 2-column grid. Drawer-style mobile nav. Reading column at 100% width minus side gutter. |
| Mobile wide | `480–700px` | Single-column. Drawer-style mobile nav. Editorial reading column at full width. |
| Tablet | `700–1024px` | 12-column grid activates. Editorial reading column at 640px centered. Desktop topbar appears. |
| Desktop | `1024–1440px` | Full container at 1192–1400px max. Three-pane application shell expands. |
| Wide desktop | `> 1440px` | Container caps at 1440px (marketing) or 1400px (editorial). Outer page gutter grows. Long-form pages use a 316px outer gutter on each side. |

## §17.2 Scaling rules

- Display and headline sizes scale linearly between the mobile and desktop values from the typography tables. Use CSS `clamp()` with the 20rem and 90rem viewport endpoints.
- Section padding clamps between the min and max values from layout.md §11.3. Major section padding reduces to 56px on mobile narrow via a discrete `@media` override.
- Grid drops from 12 columns to 2 columns below the tablet breakpoint.
- Container side gutter clamps between 32px and 64px.
- Card padding clamps between 24px and 48px.
- The conversion card width remains fixed at 448px on every breakpoint; the surrounding ground reflows.

## §17.3 Mobile typography

Below the tablet breakpoint:

- Hero h1 drops to the lower bound of its clamp (e.g., Display-1 from 72px to 42px).
- Body 2 stays at 17px — do not shrink body type below 17px on any breakpoint.
- Caption stays at 12px and Micro stays at 10px.
- Increase line-height by 5% on mobile for body type to compensate for shorter line lengths.

## §17.4 Mobile navigation

- Replace the desktop topbar's right-aligned link group with a hamburger trigger.
- The hamburger opens the drawer per the navigation system's mobile-drawer rules.
- The "primary action" CTA (e.g., the brand-button conversion link) remains visible in the topbar to the left of the hamburger.
