---
name: ios-swiftui
description: How to write and test native iOS features in Swift and SwiftUI - Swift concurrency and the main actor, state with the Observation framework (@Observable, @State, @Bindable, @Environment), NavigationStack with value-based destinations, StoreKit 2 purchases and transaction handling, on-device Core ML and Vision, passkeys through AuthenticationServices, Keychain storage, accessibility, stable accessibility identifiers, and UI tests with XCUITest and StoreKit Test. Use whenever writing, reviewing or testing Swift and SwiftUI code or iOS UI tests.
user-invocable: false
---

# iOS with Swift and SwiftUI

Read the current documentation of an API before you rely on it (`context7`: SwiftUI, StoreKit,
AuthenticationServices, Core ML, XCTest), at the deployment target the Xcode project declares. The
rules below are the checks a change passes.

## Concurrency

- Use Swift concurrency (`async`/`await`, `Task`, `AsyncSequence`), not completion handlers, for new
  code. UI state is `@MainActor`; work off the main actor is `async` and returns to it to publish.
- A view starts async work with the `.task { }` modifier (cancelled when the view disappears), or
  `.task(id:)` to restart on a value; never with a detached `Task` from `body`.
- Long-lived listeners (StoreKit transaction updates, sockets) are owned by a model object, started
  once, and cancelled when the owner goes away.
- Honour cancellation: check `Task.isCancelled` or call `try Task.checkCancellation()` in loops.

## State and data flow

- On iOS 17 and later, model types are `@Observable` classes; views own them with `@State`, receive
  them as plain properties, bind with `@Bindable`, and share app-wide ones through `@Environment`.
  On earlier targets use `ObservableObject` with `@StateObject` (owner) and `@ObservedObject`.
- A view's `body` is a pure function of its state: no side effects, no network calls, no formatting
  of data that should be computed once in the model.
- Business logic and network calls live in the model or a service the model calls, behind the
  approved API contract, never in a view.
- Keep views small: extract subviews rather than growing one `body`.

## Navigation

- Use `NavigationStack` with value-based links: `NavigationLink(value: route)` and
  `.navigationDestination(for: Route.self) { route in ... }`, and drive programmatic navigation
  through a bound `path` (`[Route]` or `NavigationPath`). `NavigationView` is deprecated.
- Routes carry ids, not whole model objects.

## StoreKit 2

- Load products with `try await Product.products(for: ids)` using the product ids the spec names.
- Purchase with `try await product.purchase(options:)` (passing `.appAccountToken(uuid)` when the
  backend links purchases to an account), then switch on the result: `.success(let verification)`,
  `.userCancelled`, `.pending`.
- Only a `.verified(transaction)` grants access; an `.unverified` result grants nothing. Call
  `await transaction.finish()` after the entitlement is recorded.
- Listen to `Transaction.updates` from app launch, and process `Transaction.unfinished` and
  `Transaction.currentEntitlements` at start, so purchases made elsewhere, renewals, refunds
  (`revocationDate`) and expirations are applied.
- Server-side validation follows the approved API contract; the app never decides entitlements the
  contract gives to the backend.

## Core ML and Vision

- Load the compiled model class Xcode generates (or `MLModel(contentsOf:)`) once and reuse it;
  loading is expensive. Run predictions off the main actor.
- For images, use Vision (`VNCoreMLRequest` with a `VNImageRequestHandler`, or the newer Vision
  Swift API on its supported targets) so scaling and orientation are handled.
- Implement only the on-device behaviour the spec defines; model quality is not a code decision.

## Passkeys and credentials

- Passkey registration: get the challenge and user id from the server, create
  `ASAuthorizationPlatformPublicKeyCredentialProvider(relyingPartyIdentifier:)`, call
  `createCredentialRegistrationRequest(challenge:name:userID:)`, and perform it with an
  `ASAuthorizationController` whose delegate returns the credential to the server.
- Sign-in: `createCredentialAssertionRequest(challenge:)` on the same provider; offer it with
  `performAutoFillAssistedRequests()` for passkey autofill when the spec asks for it.
- Both need the Associated Domains entitlement with `webcredentials:<domain>` and the server's
  `apple-app-site-association` file; without them the request fails.
- Tokens and secrets live in the Keychain, never in `UserDefaults`, source, `Info.plist` or bundled
  files. Treat URLs, universal links and push payloads as untrusted input.

## Accessibility and test hooks

- Every control has an accessibility label (system controls with text have one already; image-only
  buttons need `.accessibilityLabel`), decorative images are hidden, and related elements are
  combined with `.accessibilityElement(children: .combine)`. Support Dynamic Type: use text styles,
  not fixed font sizes.
- Give every element a test needs a stable `.accessibilityIdentifier("orders.list")`, separate from
  its user-facing label, so tests survive copy and localization changes.

## UI tests with XCUITest

- Launch with `let app = XCUIApplication()`; set `app.launchArguments` and
  `app.launchEnvironment` to put the app in a test configuration (a stubbed backend, a reset state),
  then `app.launch()`.
- Query by identifier: `app.buttons["checkout.submit"]`, `app.staticTexts["order.total"]`,
  `app.descendants(matching: .any)["id"]`; act with `tap()`, `typeText(_:)`, `swipeUp()`.
- Wait, never sleep: `XCTAssertTrue(element.waitForExistence(timeout: 5))`, or an
  `XCTNSPredicateExpectation` for a property change.
- One user journey per test; each test starts from a known state through launch arguments, never
  from the previous test.
- Purchase flows run against a StoreKit configuration file in Xcode, or `SKTestSession` in StoreKit
  Test, never against the App Store.
- A test written before the screen exists fails because the element does not exist; that is the
  intended Red. Do not create the screen to make the test launch.

## Checks before you finish

- No side effect or network call in `body`; async work tied to `.task` or a model's lifetime.
- `@Observable` state owned with `@State`; no `NavigationView`.
- Every StoreKit transaction verified before it grants access and finished after.
- No secret outside the Keychain; untrusted input validated.
- Every element a test needs has an accessibility identifier; no test sleeps.
