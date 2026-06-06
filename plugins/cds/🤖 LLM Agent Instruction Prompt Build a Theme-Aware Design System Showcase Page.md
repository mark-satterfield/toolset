Here is a step-by-step technical guide you can copy and paste directly into your prompt to instruct Claude Code (or any AI LLM Agent). It uses Next.js, Tailwind CSS v4 (or v3), and React to build a dynamic design system showcase.

------

## 🤖 LLM Agent Instruction Prompt: Build a Theme-Aware Design System Showcase Page

**Objective:**
Create a single-page theme showcase in Next.js using Tailwind CSS and React. The page must display our design system's assets and components (buttons, cards, badges, inputs, text hierarchies). All elements must smoothly change their colors, background tones, borders, and accents when switching between Light Mode, Dark Mode, and System Mode.

Follow these strict structural steps to set up the architecture, CSS variables, and mocking page.

------

## Step 1: Install Dependencies

Run the following terminal commands to install the required React theme-management package and icons for the toggle UI:

```bash
npm install next-themes lucide-react
```

------

## Step 2: Configure Global CSS & Design System Tokens

Instead of standard hardcoded Tailwind utility classes, map the design framework’s semantic colors to CSS variables. Update your main stylesheet (e.g., `src/app/globals.css`) to define the custom light/dark color tokens.

```css
@import "tailwindcss";

/* 🎨 Design System Semantic Mapping */
@theme {
  --color-bg-primary: var(--bg-primary);
  --color-bg-surface: var(--bg-surface);
  --color-text-main: var(--text-main);
  --color-text-muted: var(--text-muted);
  --color-border-subtle: var(--border-subtle);
  --color-brand-primary: var(--brand-primary);
}

/* ☀️ Light Mode Default Tokens */
:root {
  --bg-primary: #f8fafc;
  --bg-surface: #ffffff;
  --text-main: #0f172a;
  --text-muted: #64748b;
  --border-subtle: #e2e8f0;
  --brand-primary: #3b82f6;
}

/* 🌙 Dark Mode Tokens (Triggered by .dark class on <html>) */
.dark {
  --bg-primary: #0f172a;
  --bg-surface: #1e293b;
  --text-main: #f8fafc;
  --text-muted: #94a3b8;
  --border-subtle: #334155;
  --brand-primary: #60a5fa;
}

/* ⚡ Global Base Transitions */
body {
  background-color: var(--bg-primary);
  color: var(--text-main);
  transition: background-color 0.2s ease, color 0.2s ease, border-color 0.2s ease;
}
```

*(Note: If using Tailwind v3, add these custom properties to the `theme.extend` object inside `tailwind.config.js` instead, and set `darkMode: 'class'`)*

------

## Step 3: Create Theme Infrastructure (Providers & Hooks)

To handle React hydration cleanly without flash-of-unstyled-content (FOUC), create the application root wrapper and a safe theme toggle component.

## 3.1 Design the Global Theme Provider

Create `src/components/theme-provider.tsx`:

```tsx
"use client";
import * as React from "react";
import { ThemeProvider as NextThemesProvider } from "next-themes";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider attribute="class" defaultTheme="system" enableSystem>
      {children}
    </NextThemesProvider>
  );
}
```

## 3.2 Inject Providers into Next.js Layout

Wrap the application inside `src/app/layout.tsx`. Make sure to add `suppressHydrationWarning` to the `<html>` tag as required by next-themes.

```tsx
import "@/app/globals.css";
import { ThemeProvider } from "@/components/theme-provider";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
```

## 3.3 Create the Theme Switcher Dropdown

Create `src/components/theme-toggle.tsx`. This utilizes standard design system buttons allowing users to select "Light", "Dark", or sync with "System" preferences.

```tsx
"use client";
import * as React from "react";
import { useTheme } from "next-themes";
import { Sun, Moon, Monitor } from "lucide-react";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);

  // Prevent server hydration mismatch
  React.useEffect(() => setMounted(true), []);
  if (!mounted) return <div className="w-10 h-10" />;

  return (
    <div className="flex gap-1 p-1 rounded-lg border bg-bg-surface border-border-subtle w-fit">
      <button 
        onClick={() => setTheme("light")} 
        className={`p-2 rounded-md transition ${theme === 'light' ? 'bg-brand-primary text-white' : 'text-text-muted'}`}
      >
        <Sun className="w-4 h-4" />
      </button>
      <button 
        onClick={() => setTheme("dark")} 
        className={`p-2 rounded-md transition ${theme === 'dark' ? 'bg-brand-primary text-white' : 'text-text-muted'}`}
      >
        <Moon className="w-4 h-4" />
      </button>
      <button 
        onClick={() => setTheme("system")} 
        className={`p-2 rounded-md transition ${theme === 'system' ? 'bg-brand-primary text-white' : 'text-text-muted'}`}
      >
        <Monitor className="w-4 h-4" />
      </button>
    </div>
  );
}
```

------

## Step 4: Construct the Mock Showcase Page

Create a mock page at `src/app/page.tsx` using your predefined semantic semantic layout classes (`bg-bg-primary`, `bg-bg-surface`, `text-text-main`, `border-border-subtle`).

```tsx
import { ThemeToggle } from "@/components/theme-toggle";

export default function DesignSystemShowcase() {
  return (
    <main className="min-h-screen p-8 bg-bg-primary text-text-main transition-colors duration-200">
      
      {/* Header section with layout switch */}
      <header className="flex justify-between items-center pb-6 mb-8 border-b border-border-subtle">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Framework Design System</h1>
          <p className="text-sm text-text-muted">Dynamic Token Sandbox & Mode Visualizer</p>
        </div>
        <ThemeToggle />
      </header>

      {/* Component Grid Showcase */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        
        {/* Component: Cards & Typographies */}
        <section className="p-6 rounded-xl border bg-bg-surface border-border-subtle shadow-xs">
          <h2 className="text-xl font-semibold mb-2">Typography & Card Surface</h2>
          <p className="text-text-muted mb-4 text-sm leading-relaxed">
            This card surfaces background scales perfectly between light and dark modes while preserving accessibility compliance.
          </p>
          <div className="p-3 rounded-md bg-bg-primary border border-border-subtle text-xs text-text-muted">
            Tokens used: --bg-surface, --text-main, --border-subtle
          </div>
        </section>

        {/* Component: Interactive Buttons & Form Fields */}
        <section className="p-6 rounded-xl border bg-bg-surface border-border-subtle shadow-xs flex flex-col justify-between">
          <div>
            <h2 className="text-xl font-semibold mb-4">Form & Action Assets</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium mb-1 text-text-muted">Sample Input</label>
                <input 
                  type="text" 
                  placeholder="Focus framework border..." 
                  className="w-full px-3 py-2 text-sm rounded-md border bg-bg-primary border-border-subtle focus:outline-hidden focus:ring-2 focus:ring-brand-primary" 
                />
              </div>
              <div className="flex gap-3">
                <button className="px-4 py-2 text-sm font-medium rounded-md bg-brand-primary text-white hover:opacity-90 transition">
                  Brand Action
                </button>
                <button className="px-4 py-2 text-sm font-medium rounded-md border border-border-subtle bg-bg-primary text-text-main hover:bg-bg-surface transition">
                  Secondary Action
                </button>
              </div>
            </div>
          </div>
        </section>

      </div>
    </main>
  );
}
```

------

## 💡 Pro-Tips for Your AI Agent Strategy

- If Claude Code needs to mock dynamic dashboard states or complex visualizations (charts, data tables), ask it to apply **translucent background variables** (e.g., `rgba(var(--text-main-rgb), 0.1)`) inside `globals.css` so assets adapt dynamically without requiring custom asset branches.
- If Claude needs to update existing code instead of generating a new codebase, tell it to target **global framework configuration arrays** instead of hardcoding class strings into individual JSX elements.