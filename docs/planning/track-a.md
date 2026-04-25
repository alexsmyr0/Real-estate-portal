# Track A

## Mission

Track A owns the browser-facing HomeFinder experience and the user-flow backend needed to keep frontend delivery moving without waiting on the other tracks. This track intentionally carries the heaviest user-facing and critical-path load.

## Ownership Boundaries

- Own all end-user templates, CSS, and primary JavaScript.
- Own backend for registration, login, 2FA verification, sessions, favorites, inquiries, viewing requests, booking UI integration, and user-facing history pages.
- Consume catalog, reporting, recommendation, alert, booking, payment, and messaging services from Tracks K and N rather than reimplementing them.

## Tickets

### A-01: User Access Domain Baseline
Priority: Critical
Phase: P0 Existing Baseline
Depends On: None
Impacts: durable ownership of custom auth schema, login-token storage, single-session baseline, and access admin visibility
Blocks: A-02; N-02

Deliverables:
- Keep `User`, `LoginTwoFactorToken`, and `ActiveSession` aligned with the PRD and SDS.
- Keep Django auth settings and admin registration usable for email-based login.
- Preserve migration and baseline test stability around the auth domain.

Acceptance Criteria:
- Email remains the unique identifier for authentication.
- The data model represents login 2FA and one active session per user.
- Admin can inspect users, 2FA tokens, and active sessions.

Non-goals:
- Do not add registration or login page flows here.
- Do not implement email delivery or token verification logic here.
- Do not add password reset or signup email verification.

Verification gate:
- Auth migrations, settings, and admin wiring exist and remain stable under tests.

### A-02: Registration, Login, 2FA Verification, And Single-Session Backend
Priority: Critical
Phase: P1 MVP Foundation
Depends On: A-01; N-02
Impacts: registration, password login, pending 2FA state, token verification, logout, and session replacement behavior
Blocks: A-04; A-07; A-08; A-09

Deliverables:
- Implement registration, login, 2FA verification, and logout routes, forms, and services.
- Add pending-login handling so password validation does not finalize login before token verification.
- Enforce replacement of the prior active session when a new login succeeds.
- Return clear success and failure outcomes for auth flows.

Acceptance Criteria:
- A new user can register and then start the login flow.
- Valid email and password generate a 2FA token instead of creating a final session immediately.
- A valid token completes login and invalidates any previous active session for that user.
- Logout clears the authenticated browser session and active-session record consistently.

Non-goals:
- Do not build the final browser page styling for auth flows here.
- Do not add password reset or separate signup email verification.
- Do not integrate a real email provider.

Verification gate:
- Flow tests cover registration, login, valid and invalid 2FA submission, logout, and repeated-login session replacement.

### A-03: Shared Site Shell, Navigation, And Base Template System
Priority: Critical
Phase: P1 MVP Foundation
Depends On: A-01
Impacts: reusable page chrome, shared UI patterns, auth-aware navigation, and frontend consistency
Blocks: A-04; A-05; A-06; A-10; A-11; A-12; A-13; A-14; A-15

Deliverables:
- Create the base layout, shared navigation, flash message handling, and common page structure.
- Add reusable template partials for the base page, navigation, flash messages, form layouts, property cards, and empty states.
- Make the shared shell responsive enough for desktop-first use while remaining usable at 375px width.

Acceptance Criteria:
- MVP pages can extend one shared base template instead of duplicating layout markup.
- Guest and authenticated navigation states render consistently.
- Shared styling supports forms, catalog cards, and action states without page-specific duplication.

Non-goals:
- Do not implement page-specific business workflows here.
- Do not build property-detail, favorites, inquiry, booking, or reporting features here.
- Do not create a separate mobile-specific experience.

Verification gate:
- Base templates and shared static assets exist and are used by at least one implemented page flow.

### A-04: Auth Pages And Session UX
Priority: High
Phase: P2 MVP Completion
Depends On: A-02; A-03
Impacts: registration page, login page, 2FA page, logout affordances, and auth error messaging
Blocks: A-15

Deliverables:
- Build server-rendered registration, login, and 2FA verification pages.
- Add clear validation feedback, loading states where useful, and consistent session messaging.
- Expose logout through the shared authenticated navigation.

Acceptance Criteria:
- Registration, login, and 2FA pages render through the shared site shell.
- Users receive clear validation feedback for invalid credentials or tokens.
- Auth pages respect the two-step login flow and do not bypass 2FA.

Non-goals:
- Do not change the underlying auth business rules owned by A-02.
- Do not add password reset or account-recovery flows.
- Do not add profile-management or account-settings pages.

Verification gate:
- Page tests cover render paths, invalid submissions, and successful transitions through the auth flow.

### A-05: Property Discovery Landing And Catalog Frontend
Priority: Critical
Phase: P2 MVP Completion
Depends On: A-03; K-02; K-03
Impacts: landing page, public catalog UI, filter UX, property cards, pagination controls, and empty-state messaging
Blocks: A-07; A-13; A-15

Deliverables:
- Build the public landing and property catalog templates.
- Render filter controls, property cards, pagination controls, and catalog empty states.
- Preserve active filter values across catalog interactions.

Acceptance Criteria:
- Visitors can browse a landing page and move into the property catalog.
- Filter submissions preserve current values and render matching paginated result sets.
- Catalog results follow the locked filter semantics and 12-items-per-page pagination behavior.

Non-goals:
- Do not build the property detail page here.
- Do not implement favorites, inquiry, viewing, booking, or recommendation actions here.
- Do not change backend filter semantics owned by K-03.

Verification gate:
- Page tests cover landing-page render, catalog rendering, filter submissions, and pagination behavior against backend query results.

### A-06: Property Detail Frontend And Listing Presentation
Priority: Critical
Phase: P2 MVP Completion
Depends On: A-03; K-02; K-04
Impacts: property detail template, image presentation, amenity display, and availability messaging
Blocks: A-07; A-08; A-09; A-11; A-12; A-13; A-15

Deliverables:
- Build the property detail template and supporting presentation components.
- Render image galleries, amenity lists, key property facts, and availability badges.
- Reflect the locked visible/unavailable/removed listing vocabulary from the backend.

Acceptance Criteria:
- Visitors can open a property detail page for visible listings.
- Unavailable listings are readable and clearly marked unavailable.
- Removed listings are not presented as public detail pages.

Non-goals:
- Do not build catalog listing or pagination behavior here.
- Do not implement inquiry, viewing, booking, alert-subscription, or payment flows here.
- Do not redefine visibility rules owned by K-04.

Verification gate:
- Page tests cover visible and unavailable detail rendering plus removed-listing access behavior.

### A-07: Favorites Flow End-To-End
Priority: High
Phase: P2 MVP Completion
Depends On: A-02; A-05; A-06
Impacts: favorite and unfavorite actions, saved-listings page, and favorite UI state
Blocks: A-10; A-15

Deliverables:
- Implement favorite and unfavorite backend actions with authentication checks.
- Build the favorites page and saved-state UI on catalog and detail views.
- Keep favorite actions compatible with the shared logging pipeline without making logging a hard blocker.

Acceptance Criteria:
- An authenticated user can add and remove favorites from catalog, detail, and favorites views.
- Duplicate favorite submissions do not create duplicate rows.
- Favorite actions are blocked for guests.

Non-goals:
- Do not add user history or recommendation behavior here.
- Do not implement the logging pipeline itself here.
- Do not add inquiry or viewing submission flows here.

Verification gate:
- Tests cover auth gating, add/remove behavior, duplicate handling, and favorites-page rendering.

### A-08: Inquiry Flow End-To-End
Priority: Critical
Phase: P2 MVP Completion
Depends On: A-02; A-06; N-02
Impacts: inquiry forms, confirmation states, and inquiry persistence from the user-facing site
Blocks: A-10; A-15

Deliverables:
- Implement inquiry backend actions with validation and persistence.
- Build inquiry form UIs and post-submission confirmation states on the property detail page flow.
- Keep inquiry submission compatible with the shared logging pipeline and the notification service.

Acceptance Criteria:
- An authenticated user can submit an inquiry for any visible property.
- Successful inquiries persist records and trigger the inquiry confirmation email flow.
- Invalid inquiries receive clear validation feedback.

Non-goals:
- Do not implement viewing-request behavior here.
- Do not build admin inquiry-management tooling here.
- Do not implement notification or logging infrastructure internals here.

Verification gate:
- Tests cover auth gating, valid and invalid submissions, persisted records, and confirmation states.

### A-09: Viewing Request Flow End-To-End
Priority: Critical
Phase: P2 MVP Completion
Depends On: A-02; A-06; N-02
Impacts: viewing-request forms, confirmation states, and viewing persistence from the user-facing site
Blocks: A-10; A-15

Deliverables:
- Implement viewing-request backend actions with validation and persistence.
- Build viewing-request form UIs and post-submission confirmation states on the property detail page flow.
- Keep viewing submissions compatible with the shared logging pipeline and the notification service.

Acceptance Criteria:
- An authenticated user can submit a viewing request with a valid future datetime.
- Successful viewing requests persist records and trigger the viewing confirmation email flow.
- Invalid viewing requests receive clear validation feedback.

Non-goals:
- Do not implement inquiry behavior here.
- Do not turn viewing requests into rental booking requests.
- Do not implement notification or logging infrastructure internals here.

Verification gate:
- Tests cover auth gating, valid and invalid datetime submissions, persisted records, and confirmation states.

### A-10: User Activity History And Personal Dashboard
Priority: Medium
Phase: P3 Post-MVP Expansion
Depends On: A-07; A-08; A-09; N-03
Impacts: user-facing history of searches, favorites, inquiries, and viewing requests
Blocks: A-15

Deliverables:
- Build a user dashboard or history page for recent searches, saved properties, inquiries, and viewings.
- Organize data so users can distinguish between current items and older activity.
- Include empty states and sensible result limits or pagination where needed.

Acceptance Criteria:
- A user can review only their own recent searches, favorites, inquiries, and viewings.
- The page does not expose another user's data.
- Empty or low-activity accounts still receive a coherent dashboard experience.

Non-goals:
- Do not add supervisor reporting here.
- Do not redefine what gets logged or how reporting aggregates are computed.
- Do not add recommendation logic here.

Verification gate:
- Tests cover authenticated access, ownership boundaries, and rendering for empty and populated history states.

### A-11: Rental Booking Request UI
Priority: Medium
Phase: P3 Post-MVP Expansion
Depends On: A-02; A-06; N-05
Impacts: rental-only booking form, booking confirmation states, and booking initiation from the user-facing site
Blocks: A-14; A-15

Deliverables:
- Add booking request UI for rental listings only.
- Render booking date inputs, validation feedback, and submission confirmations.
- Keep booking entry points hidden or disabled for non-rental properties.

Acceptance Criteria:
- A user can submit a booking request only for rental properties.
- Booking validation errors are shown clearly when dates are invalid or incomplete.
- Successful booking submissions hand off to the booking backend and show a confirmation state.

Non-goals:
- Do not add simulated payment UI here.
- Do not support booking for residential or commercial non-rental listings.
- Do not build admin booking-management workflows here.

Verification gate:
- Tests cover rental-only UI behavior, valid and invalid booking submissions, and confirmation rendering.

### A-12: Similar Listing Alert Subscription UI
Priority: Medium
Phase: P3 Post-MVP Expansion
Depends On: A-02; A-06; N-04
Impacts: unavailable-listing alert-subscription UI and alert preference management
Blocks: A-15

Deliverables:
- Add alert-subscription UI to unavailable property detail pages.
- Let authenticated users subscribe to similar-listing alerts using the backend alert flow.
- Show clear subscribed and unsubscribed states.

Acceptance Criteria:
- Unavailable listings can expose an alert-subscription action to authenticated users.
- Users receive clear feedback when a subscription is created.
- Alert-subscription UI does not appear on removed listings.

Non-goals:
- Do not implement alert matching or alert email dispatch here.
- Do not show alert-subscription UI on available listings.
- Do not turn this ticket into recommendation UI work.

Verification gate:
- Tests cover UI visibility rules, auth gating, and successful subscription state transitions.

### A-13: Recommendation Surfaces And Personalization UI
Priority: Medium
Phase: P3 Post-MVP Expansion
Depends On: A-05; A-06; K-11
Impacts: recommendation display on agreed user-facing surfaces and recommendation-state messaging
Blocks: A-15

Deliverables:
- Add recommendation sections to the agreed landing, catalog, detail, or dashboard surfaces.
- Render recommendation cards and fallback empty states when no recommendations are available.
- Keep recommendation presentation consistent with the catalog card system.

Acceptance Criteria:
- Recommendation results can be displayed on the agreed user-facing surfaces once the backend service exists.
- Empty recommendation states do not break page layout.
- Recommendation presentation reuses the existing catalog visual language.

Non-goals:
- Do not implement recommendation ranking or generation logic here.
- Do not build a separate recommendation-specific design system.
- Do not fold user-history or alert-subscription work into this ticket.

Verification gate:
- Page tests or integrated UI tests cover recommendation rendering and empty-state behavior.

### A-14: Simulated Payment UX
Priority: Medium
Phase: P4 Final Expansion And Hardening
Depends On: A-11; N-06
Impacts: fake payment step, payment status presentation, and booking-to-payment handoff UI
Blocks: A-15

Deliverables:
- Add UI for the simulated payment step after booking where applicable.
- Render payment status messaging and failed or retryable states.
- Keep the payment experience clearly marked as a simulated university-project flow.

Acceptance Criteria:
- Users can complete a simulated payment step without leaving the application.
- Payment status updates render clearly for success and failure outcomes.
- The UI does not imply real-world payment processing.

Non-goals:
- Do not integrate a real payment gateway.
- Do not own booking backend validation or lifecycle rules here.
- Do not add invoicing, receipts, or accounting features.

Verification gate:
- Integrated tests cover booking-to-payment handoff and simulated status rendering.

### A-15: Frontend Hardening, Accessibility, And Cross-Flow Consistency
Priority: High
Phase: P4 Final Expansion And Hardening
Depends On: A-04; A-05; A-06; A-07; A-08; A-09; A-10; A-11; A-12; A-13; A-14
Impacts: final frontend consistency, accessibility, responsive QA, and cross-flow cleanup
Blocks: None

Deliverables:
- Perform final UX consistency, accessibility, and error-state cleanup across all user-facing flows.
- Verify shared components remain consistent after post-MVP feature additions.
- Harden narrow-screen layout behavior and cross-flow navigation.

Acceptance Criteria:
- Shared UI patterns remain consistent across auth, catalog, favorites, inquiries, viewings, bookings, alerts, recommendations, and payments.
- The site remains usable on narrow screens down to 375px width.
- Final cleanup does not regress completed feature flows.

Non-goals:
- Do not add new product capabilities here.
- Do not redesign backend business rules or data models here.
- Do not replace Django admin with a custom staff portal.

Verification gate:
- Cross-flow UI verification or end-to-end tests cover the main user journeys and major error states.
