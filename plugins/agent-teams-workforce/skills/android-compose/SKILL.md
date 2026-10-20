---
name: android-compose
description: How to write and test native Android features in Kotlin and Jetpack Compose - unidirectional data flow with state hoisted to a ViewModel exposing StateFlow and collected with collectAsStateWithLifecycle, side effects, type-safe Navigation Compose routes, coroutines and lifecycle, secrets in the Android Keystore, on-device ML Kit, accessibility semantics, stable test tags, and UI tests with the Compose test APIs and Espresso (finders, assertions, synchronization, idling resources, interop). Use whenever writing, reviewing or testing Kotlin and Compose code or Android UI tests.
user-invocable: false
---

# Android with Kotlin and Jetpack Compose

Read the current documentation of an API before you rely on it (`context7`: Jetpack Compose,
Compose testing, ML Kit), at the versions the project's Gradle build declares. The rules below are
the checks a change passes; each has the reason and, where it helps, one example.

## State: unidirectional data flow

- **State flows down, events flow up.** A screen composable takes plain state and callbacks; a thin
  wrapper obtains the ViewModel and passes them in. The inner composable is then previewable and
  testable without a ViewModel.
- **The ViewModel owns screen state** as one immutable UI state (`data class ...UiState`) in a
  `MutableStateFlow`, exposed read-only as `StateFlow`, changed with `update { it.copy(...) }`.
  Business logic never lives in a composable.
- **Collect with `collectAsStateWithLifecycle()`**, not `collectAsState()`: collection stops when the
  screen is not at least STARTED, so no work runs in the background.
- **Derived flows** use `stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), initial)`, so
  a configuration change does not restart the upstream.
- **`remember` holds UI element state only**; state that must survive process death uses
  `rememberSaveable` or `SavedStateHandle`.

```kotlin
@Composable
fun OrdersRoute(viewModel: OrdersViewModel = viewModel()) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    OrdersScreen(state = state, onRetry = viewModel::retry)
}
```

## Side effects and coroutines

- A suspend call from composition goes in `LaunchedEffect(key)`, keyed on what restarts it; a
  coroutine started from an event handler uses `rememberCoroutineScope()`. Never launch from the
  composable body.
- Observe Compose state as a flow with `snapshotFlow { ... }` inside an effect.
- Long-lived work belongs to `viewModelScope` (or a repository scope), never `GlobalScope`.
  Blocking I/O runs on an injected dispatcher (`Dispatchers.IO` by default) so tests can replace it.
- Cancellation is cooperative: do not catch `CancellationException` without rethrowing it.

## Navigation

- Use type-safe Navigation Compose: each destination is a `@Serializable` route class or object,
  `composable<Route> { entry -> val args = entry.toRoute<Route>() }`, and
  `navController.navigate(Route(id = ...))`. A ViewModel reads its arguments with
  `savedStateHandle.toRoute<Route>()`.
- Pass ids, never whole objects, through navigation; the destination loads the object.
- Screens receive navigation as callbacks (`onOpenOrder: (String) -> Unit`), not the `NavController`.

## Data and security

- Network and data access sit behind a repository the ViewModel calls; a composable never calls the
  network.
- The backend surface is the approved API contract only.
- Tokens and keys live in the Android Keystore (or encrypted storage backed by it), never in source,
  resources, `BuildConfig` or the manifest. Treat intents, deep links and push payloads as untrusted
  input and validate them.

## On-device ML Kit

- Build an `InputImage` from the source the spec names (`InputImage.fromMediaImage(image, rotation)`
  in a CameraX `ImageAnalysis.Analyzer`, or from a bitmap or URI) and pass it to the client's
  `process(image)`, handling both `addOnSuccessListener` and `addOnFailureListener` (or `await()` in
  a coroutine).
- Close the detector (`close()`) when its owner is destroyed, and close each `ImageProxy` after
  processing, or the camera stalls.
- A bundled model ships in the APK and works offline at once; an unbundled model is downloaded by
  Google Play services and may not be ready on first use. Use the variant the spec names and handle
  "model not yet available".
- Implement only the on-device behaviour the spec defines; model quality is not a code decision.

## Accessibility and test hooks

- Every interactive element has a role and a label: `contentDescription` on icons and images that
  carry meaning (`null` on decorative ones), `Modifier.semantics { }` or `clearAndSetSemantics` to
  merge a row into one announcement, and touch targets of at least 48 dp.
- Expose stable hooks for tests with `Modifier.testTag("orders_list")`. Set
  `Modifier.semantics { testTagsAsResourceId = true }` high in the hierarchy when UiAutomator or an
  external tool must find the tags. Never make tests depend on layout position or localized text.

## UI tests: Compose test APIs and Espresso

- `@get:Rule val rule = createAndroidComposeRule<ComponentActivity>()` (with
  `androidx.compose.ui:ui-test-manifest` as a debug dependency) to set content in isolation, or
  `createAndroidComposeRule<MainActivity>()` to drive the real activity.
- Find nodes by semantics, not by layout: `onNodeWithTag`, `onNodeWithContentDescription`,
  `onNodeWithText` (for text the spec fixes), `onAllNodes(...)`; act with `performClick`,
  `performTextInput`, `performScrollToNode`; assert with `assertIsDisplayed`, `assertTextEquals`,
  `assertIsEnabled`, `assertDoesNotExist`.
- Synchronize, never sleep. The Compose test rule waits for idle composition; for work it cannot see,
  register an `IdlingResource` (`rule.registerIdlingResource(...)`) or wait on a condition with
  `waitUntil`, `waitUntilAtLeastOneExists`, `waitUntilDoesNotExist` or `waitUntilExactlyOneExists`
  and a timeout.
- Espresso drives View-based screens (`onView(withId(...)).perform(click()).check(matches(...))`) and
  works beside Compose in the same test for hybrid screens.
- Replace the backend with a fake repository or a mock web server the test controls; a UI test never
  calls a real environment.
- A test written before the screen exists fails because the node or activity is missing; that is the
  intended Red. Do not create the screen to make the test launch.

## Checks before you finish

- No business logic, network call or blocking call in a composable.
- Every flow collected with `collectAsStateWithLifecycle`; every effect keyed.
- Routes type-safe; arguments are ids.
- No secret in source or resources; untrusted input validated.
- Every element a test needs has a test tag or semantics; no test sleeps.
