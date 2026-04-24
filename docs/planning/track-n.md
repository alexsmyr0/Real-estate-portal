# Track N

## Mission

Track N owns cross-cutting backend work: messaging, logging, alerts, booking, payments, and post-MVP operational enhancements. This track is intentionally lighter than A and K, but it still owns several dependencies that other tracks rely on.

## Ownership Boundaries

- Own notification delivery and notification persistence.
- Own activity and search logging.
- Own similar-listing alert logic, rental booking backend, and simulated payment backend.
- Own post-MVP operational enhancements such as real email delivery integration and retention automation.

## Tickets

### N-01: Notification, Logging, Alerts, And Deferred-Commerce Schema Baseline
Priority: Critical
Phase: P0 Existing Baseline
Depends On: None
Impacts: durable ownership of notification, audit, alert, booking, and payment schemas plus their admin baseline
Blocks: N-02; N-03; N-04; N-05; N-06; N-07; N-08

Deliverables:
- Keep `EmailNotification`, `SearchHistory`, `ActivityLog`, `ListingAlertSubscription`, `BookingRequest`, and `Payment` aligned with the PRD and SDS.
- Preserve the baseline admin registration for those models.
- Keep deferred post-MVP schemas present without claiming the user-facing features are already complete.

Acceptance Criteria:
- Notification, logging, alert, booking, and payment tables exist in the current domain model.
- Admin can inspect the baseline records for these models.
- The baseline schema supports later post-MVP work without needing a redesign first.

Verification gate:
- Migrations and admin wiring remain stable for the cross-cutting domain models.

### N-02: MVP Email Notification Service And Console Delivery
Priority: Critical
Phase: P1 MVP Foundation
Depends On: N-01; A-01
Impacts: 2FA delivery, inquiry and viewing confirmations, notification persistence, and reusable messaging abstractions
Blocks: A-02; A-08; A-09; N-04; N-05; N-06; N-07

Deliverables:
- Implement a reusable notification service for login 2FA and MVP confirmation emails.
- Persist notification records in `EmailNotification` while using the console backend for actual delivery.
- Support clear status handling for pending, sent, and failed notification attempts.

Acceptance Criteria:
- Login 2FA, inquiry confirmation, and viewing confirmation emails can be generated through one shared service.
- Notification records are stored with purpose, recipient, and status metadata.
- MVP delivery works without an external email provider.

Verification gate:
- Tests verify notification persistence and console-backed delivery behavior for MVP email events.

### N-03: Activity And Search Logging Pipeline
Priority: High
Phase: P1 MVP Foundation
Depends On: N-01
Impacts: auth event logging, search history persistence, and reusable interaction-audit hooks
Blocks: A-10; K-08; K-09; K-11; N-08

Deliverables:
- Implement reusable logging helpers for auth, search, and interaction events.
- Persist search criteria into `SearchHistory` and activity events into `ActivityLog`.
- Make the pipeline no-op-safe and easy for A and K tickets to call without forcing hard dependency order.

Acceptance Criteria:
- The system records auth and search activity with enough detail for later reporting.
- Feature flows can call one shared logging pipeline without duplicating logging logic.
- Logged records carry scope, action, and entity references consistently.

Verification gate:
- Tests cover creation of representative auth, search, and interaction log records.

### N-04: Similar Listing Alert Matching And Dispatch
Priority: Medium
Phase: P3 Post-MVP Expansion
Depends On: N-02; K-04
Impacts: unavailable-property subscriptions, similar-listing matching, and alert email dispatch
Blocks: A-12

Deliverables:
- Implement subscription storage and lifecycle handling for similar-listing alerts.
- Add rule-based matching between unavailable-property subscriptions and later matching listings.
- Reuse the notification service for alert delivery.

Acceptance Criteria:
- Users can hold stored alert subscriptions for unavailable properties.
- Matching logic uses property category, city, price range, bedroom minimum, and amenity overlap from the subscription model.
- Matching alerts dispatch through the notification pipeline when qualifying listings appear.

Verification gate:
- Tests cover subscription persistence, matching behavior, and alert notification creation.

### N-05: Rental Booking Request Backend
Priority: Medium
Phase: P3 Post-MVP Expansion
Depends On: N-01; N-02; K-04
Impacts: rental-only booking persistence, validation, admin-manageable booking lifecycle, and booking notifications
Blocks: A-11; N-06

Deliverables:
- Implement the backend flow for rental booking requests only.
- Validate booking inputs such as rental-only eligibility and date ranges.
- Support booking status changes and booking-related notification events.

Acceptance Criteria:
- Only rental properties can accept booking requests.
- Invalid or incomplete booking date ranges are rejected.
- Booking requests can move through an admin-manageable lifecycle after submission.

Verification gate:
- Tests cover rental-only enforcement, date validation, status updates, and booking notification creation.

### N-06: Simulated Payment Flow
Priority: Medium
Phase: P4 Final Expansion And Hardening
Depends On: N-05; N-02
Impacts: fake payment records, simulated status transitions, and booking-fee payment support without a real gateway
Blocks: A-14

Deliverables:
- Implement a simulated payment service with no real card or bank integration.
- Support payment records linked to booking flows and selected premium-use cases where needed.
- Keep payment status transitions explicit and testable.

Acceptance Criteria:
- Users can complete a simulated payment step without a real external payment gateway.
- Payment records store method, amount, purpose, and status consistently.
- Simulated payments remain clearly separate from production-grade payment processing.

Verification gate:
- Tests cover payment creation, allowed status transitions, and booking linkage.

### N-07: Production Email Provider Integration
Priority: Medium
Phase: P4 Final Expansion And Hardening
Depends On: N-02
Impacts: real email delivery integration and provider-ready configuration
Blocks: None

Deliverables:
- Add a real email-provider integration path while preserving the existing notification service abstraction.
- Keep console delivery usable for development while allowing production-like delivery through configuration.
- Document the provider-switching configuration path.

Acceptance Criteria:
- The system can be configured to send email through a real provider after the MVP.
- Notification persistence continues to work regardless of delivery backend.
- Development and demo environments can still use console delivery safely.

Verification gate:
- Configuration tests or integration checks verify provider switching without breaking notification persistence.

### N-08: Retention Automation For Log-Style Records
Priority: Medium
Phase: P4 Final Expansion And Hardening
Depends On: N-03
Impacts: scheduled cleanup of log-style records under the 90-day retention policy
Blocks: None

Deliverables:
- Add automated cleanup for `activity_logs`, `search_history`, and `email_notifications` records older than 90 days.
- Keep cleanup scoped to log-style data only.
- Document the execution path for the cleanup job.

Acceptance Criteria:
- Retention automation applies only to `activity_logs`, `search_history`, and `email_notifications`.
- Records older than 90 days are eligible for cleanup.
- Primary business entities such as properties, favorites, inquiries, viewing requests, bookings, and users are not deleted by this job.

Verification gate:
- Retention-job tests verify cleanup behavior against dated records while preserving non-target tables.
