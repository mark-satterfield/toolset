---
name: web-frontend-coding
description: How to write React web and mobile (React Native, Expo) front ends that pass the Rules of React lints and an accessibility review the first time — Rules of Hooks, effects only for synchronising with external systems and with complete dependencies, pure render, component and state design, WCAG 2.2 AA semantics, labels, focus, keyboard, contrast and target size, safe rendering of untrusted data and URLs, data fetching with loading, empty and error states, performance from evidence, and composing from the project's design system. Use whenever writing, editing, refactoring, reviewing or testing React components, hooks or front-end pages (.tsx, .jsx), together with typescript-coding.
user-invocable: true
---

# React front ends: pure, accessible and safe by construction

A component is a pure function from props, state and context to markup; everything else (fetching, subscriptions,
timers, writing to the page outside React) happens in event handlers or effects. Write components that way and the
Rules of React lints have nothing to report, the React Compiler can optimise them, and the page behaves the same every
time it renders. Accessibility and safe rendering are written in the same pass, not added afterwards.

These rules apply to every React component, hook and page an agent writes, changes or reviews. A reviewer judges the
code against them.

**Load `typescript-coding` too.** Every rule there applies to front-end code; this skill covers what is specific to
React and to the browser or device. When the project has a design system skill or design tokens, load and follow them
as well (Design system).

## How to read this skill

- Every rule has one form: the instruction, then the reason, then at most one example.
- An example is two labelled code blocks, "Instead of" and "Write". The "Instead of" block shows the habit the rule
  bans. An example illustrates its rule; the rule covers every case its text describes, not only the case shown.
- Examples are shortened: imports and types are trimmed unless the rule is about them.
- A name in parentheses, such as (`exhaustive-deps`) or (WCAG 2.4.7), names the lint rule or the WCAG 2.2 success
  criterion that checks the same thing.

## Habits to replace on sight

| Do not | Do instead | Section |
|---|---|---|
| A hook inside a condition, loop or after an early return | Every hook at the top level of the component, before any return | Rules of Hooks |
| `useEffect` that copies props or state into other state | Compute the value during render | Effects |
| A dependency array that leaves out a value the effect reads | Every reactive value listed, or the effect restructured | Effects |
| `<div onClick>` as a button or link | `<button>` or `<a href>` | Accessibility |
| An input with only a placeholder | A `<label>` tied to the input | Accessibility |
| `dangerouslySetInnerHTML` with fetched or user content | Render text as children, or sanitise first | Safe rendering |
| A component defined inside another component | Every component defined at module level | Components |
| `key={index}` on a list that can change order | A stable id from the data | Components |

## Rules of Hooks

- Call hooks only at the top level of a React function component or of a custom hook, before any early return; never
  inside a condition, a loop, a nested function, a `try`/`catch`, or at module level (`rules-of-hooks`). The reason:
  React identifies each hook by its call order, so a hook that is called on one render and not the next attaches
  state to the wrong hook.

  Instead of:

  ```tsx
  function Profile({ userId }: ProfileProps) {
    if (userId === undefined) {
      return <SignInPrompt />;
    }
    const [isEditing, setIsEditing] = useState(false);
    // ...
  }
  ```

  Write:

  ```tsx
  function Profile({ userId }: ProfileProps) {
    const [isEditing, setIsEditing] = useState(false);
    if (userId === undefined) {
      return <SignInPrompt />;
    }
    // ...
  }
  ```

- Name every custom hook `useSomething`, and call hooks only from components and custom hooks. A plain function
  that calls a hook is a custom hook and takes the `use` prefix.

## Pure render

- Keep render pure: the same props, state and context always produce the same output, and rendering changes nothing
  outside the component (`purity`). No network calls, timers, `Math.random()`, `Date.now()`, logging side effects or
  writes to variables outside the component during render. The reason: React renders a component as often as it
  needs to (twice in development Strict Mode), so a side effect in render runs an unpredictable number of times.
- Never mutate props, state, context, or values passed to a hook or to JSX (`immutability`). Create a new object or
  array (`[...items, newItem]`, `{ ...draft, title }`) and set it.
- Never read or write `ref.current` during render (`refs`). A ref is for values that do not affect the output (a DOM
  node, a timer id); read and write it in event handlers and effects. A value that affects the output is state.
- Never call a state setter unconditionally during render (`set-state-in-render`); it renders again forever.

## Effects

- Use an effect only to synchronise with a system outside React: a subscription, a browser API, a non-React widget, a
  connection. The reason: an effect runs after the screen updates, so using it to compute values causes an extra
  render with stale data first. A value derived from props or state is computed during render; work caused by a user
  action belongs in that action's event handler.

  Instead of:

  ```tsx
  const [visibleTodos, setVisibleTodos] = useState<Todo[]>([]);
  useEffect(() => {
    setVisibleTodos(todos.filter((todo) => !todo.isDone));
  }, [todos]);
  ```

  Write:

  ```tsx
  const visibleTodos = todos.filter((todo) => !todo.isDone);
  ```

- Do not set state synchronously at the top of an effect to mirror other state (`set-state-in-effect`); compute it
  during render, or reset a component's state by giving it a different `key`.
- List every reactive value the effect reads (props, state, and anything declared in the component body) in its
  dependency array (`exhaustive-deps`). When a dependency makes the effect run too often, change the code, not the
  array: move an object or function the effect needs inside the effect, move a value that never changes outside the
  component, or read the latest value through the React version's effect-event API (`useEffectEvent`) where it is
  available. Never silence the rule; a missing dependency is a stale-data bug.
- Return a cleanup function from every effect that subscribes, starts a timer, opens a connection or starts a
  request, and make it undo exactly that: unsubscribe, clear the timer, close the connection, abort the request with
  an `AbortController`. The reason: the effect runs again whenever its dependencies change and on every remount in
  Strict Mode; without cleanup each run leaves the previous one running.
- Handle a promise inside an effect explicitly (`typescript-coding`, Promises): an effect callback cannot be
  `async`; start the async work inside it and ignore a result that arrives after cleanup.

## Components

- Define every component at module level, never inside another component's body (`static-components`). The reason:
  a component defined during render is a new type on every render, so React unmounts and remounts it, losing its
  state and focus each time.
- Give every element of a rendered list a `key` that is stable and unique among its siblings, taken from the data (an
  id), not the array index when the list can be reordered, filtered or inserted into. The reason: React matches
  elements across renders by key; an index key attaches one item's state to another.
- Keep components small and single-purpose: one component renders one thing; extract a part that has its own state or
  its own reason to change. Type props with a `readonly` interface named `<Component>Props`.
- Pass data down through props and events up through callbacks. Use context for values that many distant components
  need and that change rarely (the signed-in user, the theme), not as a general state store.
- Wrap each independently failing region of a page in an error boundary, so an error in one widget shows a fallback
  for that widget instead of a blank page.

## State

- Keep state minimal: store only what cannot be computed from props or other state. Two pieces of state that must
  always agree are one piece of state.
- Keep state as close as possible to where it is used, and lift it to the nearest common parent only when two
  components need it.
- Model state that has several modes (idle, loading, loaded, failed) as one discriminated union, not as several
  booleans that can contradict each other (`isLoading` and `hasError` both true).
- Use the functional update form (`setCount((count) => count + 1)`) when the next state depends on the previous one.

## Data fetching

- Fetch through the project's data layer (the framework's server data loading, or the query library the project
  uses), not with ad-hoc `fetch` calls in effects. The reason: the data layer handles caching, deduplication,
  cancellation and race conditions that an effect-based fetch gets wrong.
- Render every state of every request: loading, empty, error (with a way to retry) and loaded. A request with no
  error state leaves the user looking at a spinner forever when it fails.
- Validate every response at the boundary (`typescript-coding`, Types): the server's data is `unknown` until a schema
  has parsed it.

## Accessibility (WCAG 2.2 AA)

Accessibility is part of correctness: a control that cannot be reached by keyboard or announced by a screen reader is
a broken control.

- Use the native element for its purpose: `<button>` for actions, `<a href>` for navigation, `<form>` with
  `onSubmit` for forms, headings in order (`h1` to `h6` without skipping levels), lists for lists, `<main>`, `<nav>` and
  `<header>` landmarks (WCAG 1.3.1, 4.1.2). The reason: native elements bring keyboard handling, focus and the right
  screen reader role for free; a `<div>` with `onClick` brings none of them.

  Instead of:

  ```tsx
  <div className="save" onClick={saveDraft}>Save</div>
  ```

  Write:

  ```tsx
  <button type="button" onClick={saveDraft}>Save</button>
  ```

- Give every form control a visible label tied to it (`<label htmlFor>` or wrapping), and connect help text and error
  messages with `aria-describedby` (WCAG 1.3.1, 3.3.2). A placeholder is not a label: it disappears on input.
- Give every meaningful image a text alternative (`alt`) that says what it conveys; give a decorative image `alt=""`
  (WCAG 1.1.1). Give an icon-only button an accessible name (`aria-label`).
- Make everything usable with the keyboard alone, in a logical order, with no keyboard trap (WCAG 2.1.1, 2.1.2,
  2.4.3). Never put a positive `tabIndex` on anything.
- Keep the focus indicator visible (WCAG 2.4.7) and never hidden behind sticky headers or overlays (WCAG 2.4.11). Never
  remove `outline` without a replacement of at least the same visibility.
- Manage focus on changes of context: move focus into a dialog when it opens, keep it there while it is open, and
  return it to the control that opened it when it closes. Prefer the native `<dialog>` element or the design system's
  dialog, which do this.
- Meet contrast: 4.5:1 for normal text, 3:1 for large text and for the boundaries of controls and focus indicators
  (WCAG 1.4.3, 1.4.11). Never convey information by colour alone (WCAG 1.4.1).
- Make pointer targets at least 24 by 24 CSS pixels, or space them so they do not overlap (WCAG 2.5.8). On mobile,
  follow the platform's larger guidance (44 by 44 points on iOS, 48 by 48 dp on Android).
- Announce results of asynchronous actions that do not move focus (saved, failed, three results found) through a
  live region (`role="status"` or `aria-live="polite"`; `role="alert"` for errors) (WCAG 4.1.3).
- Use ARIA only where no native element expresses the role, and then follow the WAI-ARIA Authoring Practices pattern
  for that widget completely (roles, states and keyboard). Incorrect ARIA is worse than none.
- Respect user settings: honour `prefers-reduced-motion`, allow zoom to 200% without loss of content, and never set
  `user-scalable=no`.
- In React Native, give every touchable element `accessibilityRole` and an `accessibilityLabel` when its content is
  not text, and group related elements with `accessible`.

## Safe rendering

- Render untrusted content as text: put it in JSX children or attributes, which React escapes. Never pass fetched,
  stored or user-supplied content to `dangerouslySetInnerHTML`; when HTML from outside must be rendered, sanitise it
  with a maintained sanitiser (for example DOMPurify) immediately before rendering. The reason: unescaped HTML is
  cross-site scripting.
- Validate every URL that comes from data before putting it in `href`, `src` or `window.location`: allow only
  `https:` (and `mailto:` or relative paths where intended). React does not block `javascript:` URLs in every
  version.
- Open external links that use `target="_blank"` with `rel="noopener noreferrer"`.
- Never put a secret in front-end code or in a public build-time variable (`NEXT_PUBLIC_*`, `EXPO_PUBLIC_*`,
  `VITE_*`): everything in the bundle is readable by anyone. Secrets stay on the server.
- Store tokens where script cannot read them (HTTP-only, `Secure`, `SameSite` cookies) when the architecture allows;
  never in `localStorage` for a long-lived credential.
- Write no inline scripts or inline event handler strings, so the page works under a strict Content Security Policy.

## Performance

- Optimise from evidence, not by habit. Add `useMemo`, `useCallback` or `memo` only when a measurement (the React
  Profiler, a slow interaction) shows a cost, or where an API requires a stable identity. Where the project uses the
  React Compiler, write no manual memoisation at all; the compiler adds it. The reason: unneeded memoisation adds
  dependency arrays that can go stale and code that must be read.
- Split code by route and load rarely used heavy components lazily (`lazy` with `Suspense`, or the framework's
  dynamic import).
- Give every image its dimensions (or an aspect ratio) and the right size and format for its slot, so the layout does
  not shift (Cumulative Layout Shift) and the page does not download more than it shows.
- Virtualise a list that can hold hundreds of rows.
- Add a dependency only after checking its bundle cost against what it replaces.

## Design system

- When the project provides a design system (components, tokens, a design system skill or configuration file),
  compose every page from its components and style only with its tokens. Never hard-code a colour, spacing value,
  font size, radius or shadow. The reason: the design system carries the decided look and the accessibility work
  (contrast, focus styles, target sizes) already done once; a hand-made copy drifts from both.
- Load the project's design system skill before writing UI when one exists, and follow its rules for which component
  to use and how.

## Tests

- Test components through what the user sees and does: query by role and accessible name (`getByRole("button", {
  name: "Save" })`), act through user events, and assert on the result. The reason: such tests survive refactoring
  and fail when the accessible name is missing, which is itself a defect.

## The safety net

Where the repository's hooks run ESLint (with the React Hooks rules), the TypeScript compiler and Prettier after each
edit and at commit, fix every finding they report and do not run those checks yourself; where no hook runs them, run
them on the changed files before finishing. Lints check the Rules of React; they do not check most of accessibility,
so the rules above are written in, not waited for. Where the project has an accessibility audit (for example the
`a11y-audit` skill), use it to verify a page before it is finished.
