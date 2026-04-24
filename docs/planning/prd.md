# HomeFinder Product Requirements Document

## Purpose

This document defines what HomeFinder must do, who it serves, what belongs in the MVP, and what is intentionally deferred until later phases.

## Product Overview

HomeFinder is a web-based real estate portal for browsing and inquiring about residential, commercial, and rental properties. The product is intended to make property discovery easier, support direct user-to-platform interactions, and give staff a manageable way to maintain listings and handle incoming activity.

Primary goals:
- streamline property discovery
- support inquiry and viewing workflows
- support staff-side listing and interaction management
- provide a credible university-project MVP with room to expand later

## User Types

### Guest Visitor
- Can access the public property browsing experience.
- Can review property details.
- Cannot favorite properties, submit inquiries, or request viewings until authenticated.

### Registered User
- Registers with email and password.
- Logs in with email/password plus email-based 2FA.
- Browses, filters, favorites, inquires about, and requests viewings for properties.

### Admin
- Manages property listings through Django admin.
- Reviews and updates inquiries and viewing requests through Django admin.

### Customer Service Supervisor
- Post-MVP read-only reporting user.
- Reviews monthly summaries such as inquiries, saved properties, and search trends.

## Product Goals

- Deliver an end-to-end MVP that can be demonstrated as a working web portal.
- Keep implementation simple enough for a 3-person team using Django templates and light JavaScript.
- Avoid overcommitting to complex features before the MVP is stable.
- Preserve a clean path to post-MVP additions without rebuilding the core architecture.

## MVP Scope

### Included
- User registration.
- Login with email and password.
- Login 2FA using an email token.
- One active session per user, where a new login invalidates the old session.
- Property listing page.
- Property detail page.
- Search and filtering by location, price range, category, bedrooms, and amenities where data exists.
- Add property to favorites.
- Remove property from favorites.
- Submit an inquiry for any property type.
- Submit a viewing request for any property type.
- Generate confirmation emails for login 2FA, inquiries, and viewing requests.
- Admin property CRUD through Django admin.
- Admin handling of inquiries and viewing requests through Django admin.
- Basic backend activity logging and search logging.

### Excluded From MVP
- Personalized recommendations.
- Similar-listing alerts for unavailable properties.
- Rental booking requests.
- Simulated payments.
- Supervisor dashboard or reporting UI.
- User-facing history page.
- Real email provider integration.
- Mobile app support.
- Advanced GDPR workflows beyond minimal data collection.
- Implemented maintenance mode.
- Automated log-retention cleanup.

## Post-MVP Scope

Planned later additions:
- Personalized recommendations.
- Similar-listing alerts for unavailable properties.
- Rental booking request flow.
- Simulated payment flow after booking exists.
- Supervisor monthly reports using tables.
- User-facing activity and history page.
- Real email delivery.
- Optional compliance and retention automation if time permits.

## Core User Journeys

### Registration
1. Visitor opens the registration page.
2. Visitor submits email, password, and any optional minimal profile fields exposed by the form.
3. System creates a user account.
4. User can continue into the login flow.

### Login With Email 2FA
1. User submits email and password.
2. System validates credentials and generates a short-lived 2FA token.
3. Token is sent through the MVP email mechanism.
4. User submits the token on the verification page.
5. System creates the active session and invalidates any prior session for that user.

### Property Browse And Filter
1. Visitor or user opens the property catalog.
2. User filters by location, price range, category, bedrooms, and available amenities.
3. System returns matching active listings.
4. User opens a property detail page for deeper inspection.

### Property Detail Review
1. Visitor or user opens a property detail page.
2. System displays title, description, category, location, price, bedrooms, amenities, and images where available.
3. Authenticated users can continue into favorites, inquiries, and viewing requests.

### Save To Favorites
1. Authenticated user selects a property from the list or detail page.
2. User saves it to favorites.
3. System records the favorite and prevents duplicates.

### Remove From Favorites
1. Authenticated user opens favorites or a property detail page.
2. User removes a saved property.
3. System deletes the favorite entry and updates the visible state.

### Submit Inquiry
1. Authenticated user opens a property detail page.
2. User submits a free-text inquiry.
3. System stores the inquiry, marks it as open, logs the interaction, and generates a confirmation email.

### Schedule Viewing
1. Authenticated user opens a property detail page.
2. User selects a requested date and time and may include a note.
3. System stores the request as pending, logs the interaction, and generates a confirmation email.

### Admin Adds Or Updates Property
1. Admin opens Django admin.
2. Admin creates or edits a property listing, its metadata, and related assets.
3. System persists the changes and makes them available to the browse experience.

### Admin Reviews Inquiries And Viewings
1. Admin opens Django admin.
2. Admin reviews stored inquiries and viewing requests.
3. Admin updates statuses or notes as needed.

## Functional Requirements

### Authentication And Session Control
- The system must allow user registration with email and password.
- The system must authenticate users with email and password.
- The system must require a valid email-delivered 2FA token before finishing login.
- The system must permit only one active session per user at a time.
- The system must invalidate the old session when a new login succeeds.
- The system must use minimal personal data collection consistent with the project scope.

### Property Catalog And Search
- The system must support property categories for residential, commercial, and rental listings.
- The system must show a property listing page and property detail page.
- The system must support filtering by location, price range, category, bedrooms, and amenities where supported by available listing data.
- The system must hide removed listings from the public catalog.

### Favorites
- The system must allow authenticated users to add properties to favorites.
- The system must allow authenticated users to remove properties from favorites.
- The system must prevent duplicate favorites for the same user and property.

### Inquiries
- The system must allow authenticated users to submit inquiries for any property type.
- The system must store inquiry content and status.
- The system must generate an inquiry confirmation email.

### Viewing Requests
- The system must allow authenticated users to request a viewing for any property type.
- The system must store requested datetime, note, and request status.
- The system must generate a viewing confirmation email.

### Notifications And Email
- The system must generate email-based 2FA tokens during login.
- The system must generate confirmation emails for inquiries and viewing requests.
- The MVP email mechanism may be non-production and must still demonstrate the full flow.

### Admin Operations
- Admins must manage property listings through Django admin.
- Admins must review and manage inquiries through Django admin.
- Admins must review and manage viewing requests through Django admin.

### Logging And Audit
- The system must log key authentication, interaction, and search events in the backend.
- The system must retain the data model necessary to support later reporting and auditing work.

### Post-MVP Features
- The system should later support supervisor reporting.
- The system should later support unavailable-property alerts.
- The system should later support rental booking requests.
- The system should later support simulated payments.
- The system should later support recommendations.
- The system should later support a user-facing history page.

## Non-Functional Requirements

- HomeFinder operates as a web client backed by server-side storage.
- Password handling must rely on Django authentication security mechanisms.
- The project follows GDPR-style minimal data collection.
- The project enforces one active session per user.
- Weekly downtime of up to 30 minutes is a documented operational constraint, not an MVP feature to build.
- MVP email uses a fake or console delivery mechanism suitable for development and demonstration.
- Activity and interaction logs are conceptually retained for 3 months, but automated cleanup is deferred.
- Future mobile support is a roadmap note only and is not part of the current deliverable.

## Success Criteria

The MVP is successful when:
- a user can register, log in with email 2FA, browse and filter properties, save favorites, send inquiries, and request viewings
- an admin can manage listings and review interactions through Django admin
- the system demonstrates end-to-end token and confirmation email flows without needing an external email provider
- the architecture remains simple enough for parallel delivery by the team

## Out Of Scope And Explicit Deferrals

The following are intentionally out of the MVP so later ticketing stays honest:
- personalized recommendations
- similar-listing alerts
- rental booking requests
- simulated payments
- supervisor reporting UI
- user-facing history pages
- real email integration
- custom staff portal work outside Django admin
- mobile application support
- automated maintenance mode
- automated log cleanup
