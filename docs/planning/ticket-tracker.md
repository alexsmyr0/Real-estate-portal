# Ticket Progress Tracker

This file tracks delivery progress for the final `A / K / N` track split.

Detailed ticket definitions live in:

- `docs/planning/track-a.md`
- `docs/planning/track-k.md`
- `docs/planning/track-n.md`

Canonical planning inputs remain in:

- `docs/planning/prd.md`
- `docs/planning/sds.md`

## Update Rules

1. Keep each ticket in the line format: status + ticket ID + short description + dependency fields.
2. Use `[x]` only when the verification gate in the owning track file is satisfied.
3. Use `[-]` only when a meaningful subset of that ticket already exists in code.
4. Current statuses are placeholders until the baseline code audit in step 3.
5. Keep `Depends on` and `Blocks` synchronized with the owning track file when ticket definitions change.
6. Do not remove completed tickets from the tracker.

## Status Legend

- `[ ]` = Not Started
- `[-]` = Partially Implemented / In Progress
- `[x]` = Done

## Phase Definitions

- `P0 Existing Baseline`: repo-supported foundations that already exist in full or in part and must be audited, preserved, or tightened before feature delivery.
- `P1 MVP Foundation`: the minimum unblockers and shared infrastructure needed before the full MVP user flows can be completed.
- `P2 MVP Completion`: the end-user and staff-facing features required for the agreed MVP demonstration.
- `P3 Post-MVP Expansion`: deferred features that extend the product after the MVP boundary is complete.
- `P4 Final Expansion And Hardening`: final post-MVP integrations, operational enhancements, and cross-flow cleanup after the major feature areas exist.

## Execution Policy (Low-Blocking First)

1. Respect the canonical phase order: `P0 -> P1 -> P2 -> P3 -> P4`.
2. Inside each phase, prioritize tickets that unblock the most other tracks.
3. Track `A` owns browser UI/UX plus auth and user-flow backend.
4. Track `K` owns catalog, search, admin, seed data, reporting, and recommendation backend.
5. Track `N` owns notifications, logging, alerts, booking, payments, and messaging or retention operations.
6. Track `A` intentionally carries the heaviest user-facing and critical-path load.
7. When two tickets are both available, prefer the one that reduces cross-track waiting first and personal preference second.

## Summary Snapshot

- Total tickets: `34`
- Done: `0`
- Partially Implemented: `0`
- Not Started: `34`
- Baseline audit status: `Pending step 3`

## Low-Blocking Claim Queue (Global)

Use this as the default claim order for the next wave of work:

1. **Q0 P0 Baseline Lock-In**: `A-01`, `K-01`, `N-01`
2. **Q1 P1 MVP Unblockers**: `N-02`, `N-03`, `A-02`, `A-03`, `K-02`, `K-04`, `K-03`, `K-05`
3. **Q2 P2 MVP Feature Completion**: `A-04`, `A-05`, `A-06`, `A-07`, `A-08`, `A-09`, `K-06`, `K-07`
4. **Q3 P3 Post-MVP Growth**: `A-10`, `A-11`, `A-12`, `A-13`, `K-08`, `K-09`, `K-10`, `K-11`, `N-04`, `N-05`
5. **Q4 P4 Final Expansion And Hardening**: `A-14`, `A-15`, `N-06`, `N-07`, `N-08`

## Ticket ID Index

- Track A: `A-01` through `A-15`
- Track K: `K-01` through `K-11`
- Track N: `N-01` through `N-08`

## Ordered Tickets By Track

### Track A

- [ ] **A-01** P0 - User Access Domain Baseline | Custom user auth, 2FA token, and active-session schema baseline. (Depends on: None) | Blocks: A-02; N-02
- [ ] **A-02** P1 - Registration, Login, 2FA Verification, And Single-Session Backend | Auth backend flow for registration, login, token verification, logout, and session replacement. (Depends on: A-01; N-02) | Blocks: A-04; A-07; A-08; A-09
- [ ] **A-03** P1 - Shared Site Shell, Navigation, And Base Template System | Shared browser shell, layout primitives, responsive navigation, and reusable UI partials. (Depends on: A-01) | Blocks: A-04; A-05; A-06; A-10; A-11; A-12; A-13; A-14; A-15
- [ ] **A-04** P2 - Auth Pages And Session UX | Registration, login, 2FA, and logout pages built on the shared site shell. (Depends on: A-02; A-03) | Blocks: A-15
- [ ] **A-05** P2 - Property Discovery Landing And Catalog Frontend | Landing page, public catalog, filters, pagination, and result-state UX. (Depends on: A-03; K-02; K-03) | Blocks: A-07; A-13; A-15
- [ ] **A-06** P2 - Property Detail Frontend And Listing Presentation | Detail-page UI, image presentation, amenity display, and availability messaging. (Depends on: A-03; K-02; K-04) | Blocks: A-07; A-08; A-09; A-11; A-12; A-13; A-15
- [ ] **A-07** P2 - Favorites Flow End-To-End | Favorite and unfavorite backend actions plus saved-listings UX. (Depends on: A-02; A-05; A-06) | Blocks: A-10; A-15
- [ ] **A-08** P2 - Inquiry Flow End-To-End | Inquiry backend actions, forms, confirmation states, and email integration. (Depends on: A-02; A-06; N-02) | Blocks: A-10; A-15
- [ ] **A-09** P2 - Viewing Request Flow End-To-End | Viewing backend actions, datetime validation, confirmation states, and email integration. (Depends on: A-02; A-06; N-02) | Blocks: A-10; A-15
- [ ] **A-10** P3 - User Activity History And Personal Dashboard | User-facing history for searches, favorites, inquiries, and viewings. (Depends on: A-07; A-08; A-09; N-03) | Blocks: A-15
- [ ] **A-11** P3 - Rental Booking Request UI | Rental-only booking initiation, validation feedback, and confirmation UX. (Depends on: A-02; A-06; N-05) | Blocks: A-14; A-15
- [ ] **A-12** P3 - Similar Listing Alert Subscription UI | Alert-subscription UX for unavailable property pages. (Depends on: A-02; A-06; N-04) | Blocks: A-15
- [ ] **A-13** P3 - Recommendation Surfaces And Personalization UI | User-facing recommendation display on agreed site surfaces. (Depends on: A-05; A-06; K-11) | Blocks: A-15
- [ ] **A-14** P4 - Simulated Payment UX | Fake payment-step UI and payment-status messaging after booking. (Depends on: A-11; N-06) | Blocks: A-15
- [ ] **A-15** P4 - Frontend Hardening, Accessibility, And Cross-Flow Consistency | Final UI consistency, accessibility, responsive QA, and cross-flow cleanup. (Depends on: A-04; A-05; A-06; A-07; A-08; A-09; A-10; A-11; A-12; A-13; A-14) | Blocks: None

### Track K

- [ ] **K-01** P0 - Property Catalog Domain Baseline | Property, amenity, image, and listing-status schema baseline. (Depends on: None) | Blocks: K-02; K-04; K-05; K-06; A-05; A-06; N-04; N-05
- [ ] **K-02** P1 - Public Catalog Read Routes And Query Service | Public property read routes and reusable catalog query helpers. (Depends on: K-01) | Blocks: K-03; A-05; A-06
- [ ] **K-03** P1 - Search, Filter, And Pagination Backend | Catalog filtering with locked location, amenity, and pagination semantics. (Depends on: K-02) | Blocks: A-05; K-08; K-09; K-11
- [ ] **K-04** P1 - Property Detail Availability Rules And Listing Visibility | Backend rules for visible, unavailable, and removed property detail behavior. (Depends on: K-01) | Blocks: A-06; K-06; N-04; N-05; K-11
- [ ] **K-05** P1 - Demo Catalog Seed Data And Test Fixtures | Repeatable demo and test data for listings, amenities, images, and statuses. (Depends on: K-01) | Blocks: K-08; K-09; K-10; K-11
- [ ] **K-06** P2 - Admin Listing CRUD | Django admin usability for listing creation and maintenance. (Depends on: K-01; K-04) | Blocks: None
- [ ] **K-07** P2 - Interaction Management Admin | Django admin usability for inquiry and viewing-request management. (Depends on: K-05) | Blocks: None
- [ ] **K-08** P3 - Supervisor Inquiry And Saved-Property Reporting Aggregations | Monthly aggregate metrics for inquiries and favorites. (Depends on: N-03; K-05) | Blocks: K-10
- [ ] **K-09** P3 - Search Trends Aggregation Service | Top-10 monthly search trends for cities, categories, and price bands. (Depends on: K-03; N-03; K-05) | Blocks: K-10
- [ ] **K-10** P3 - Supervisor Reporting Read-Only Pages | Read-only reporting pages for supervisor and admin roles. (Depends on: K-08; K-09) | Blocks: None
- [ ] **K-11** P3 - Personalized Recommendations Backend | Rule-based recommendations using catalog similarity and user-behavior signals. (Depends on: K-03; K-04; N-03; K-05) | Blocks: A-13

### Track N

- [ ] **N-01** P0 - Notification, Logging, Alerts, And Deferred-Commerce Schema Baseline | Baseline schema for notifications, logs, alerts, bookings, and payments. (Depends on: None) | Blocks: N-02; N-03; N-04; N-05; N-06; N-07; N-08
- [ ] **N-02** P1 - MVP Email Notification Service And Console Delivery | Shared email service for 2FA and MVP confirmations with notification persistence. (Depends on: N-01; A-01) | Blocks: A-02; A-08; A-09; N-04; N-05; N-06; N-07
- [ ] **N-03** P1 - Activity And Search Logging Pipeline | Shared logging and search-history pipeline with no-op-safe helper hooks. (Depends on: N-01) | Blocks: A-10; K-08; K-09; K-11; N-08
- [ ] **N-04** P3 - Similar Listing Alert Matching And Dispatch | Rule-based alert subscriptions and similar-listing notification delivery. (Depends on: N-02; K-04) | Blocks: A-12
- [ ] **N-05** P3 - Rental Booking Request Backend | Rental-only booking persistence, validation, statuses, and booking notifications. (Depends on: N-01; N-02; K-04) | Blocks: A-11; N-06
- [ ] **N-06** P4 - Simulated Payment Flow | Fake payment processing and explicit payment-status transitions without a real gateway. (Depends on: N-05; N-02) | Blocks: A-14
- [ ] **N-07** P4 - Production Email Provider Integration | Real email-provider support while preserving the shared notification abstraction. (Depends on: N-02) | Blocks: None
- [ ] **N-08** P4 - Retention Automation For Log-Style Records | 90-day cleanup for activity logs, search history, and email notification records. (Depends on: N-03) | Blocks: None
