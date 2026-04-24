# HomeFinder Software Design Specification

## Purpose

This document defines the agreed technical implementation shape for HomeFinder, covering the MVP architecture and the planned path for post-MVP expansion.

## Architecture Overview

HomeFinder is designed as a Django monolith backed by MySQL. The system uses server-rendered HTML through Django templates and only light JavaScript for progressive enhancement. Staff operations are handled through Django admin. There is no separate frontend app, no SPA architecture, and no mobile implementation in the current scope.

Locked technical choices:
- Django monolith
- MySQL database
- server-rendered HTML via Django templates
- light JavaScript only where it improves UX
- Django admin for staff operations
- no separate frontend application
- no SPA architecture
- no mobile implementation now

## High-Level Subsystems

### Users / Auth
- Custom user model using email as the login identifier.
- Registration flow.
- Login flow.
- Email 2FA token issuance and verification.
- Single active session enforcement.

### Properties / Catalog
- Property entities, amenities, and images.
- Public property listing and detail experience.
- Filtering and search behavior.

### Interactions
- Favorites.
- Property inquiries.
- Viewing requests.
- Search history.
- Activity logging.

### Notifications
- Email notifications for login 2FA.
- Email notifications for inquiry and viewing confirmations.

### Staff
- Django admin for property and interaction management.
- Post-MVP read-only supervisor reporting area.

### Future Extensions
- Similar-listing alerts.
- Rental booking requests.
- Simulated payments.
- Recommendations.
- User-facing history pages.

## Current Baseline

The current repository already contains meaningful backend baseline work:
- Django project configuration is in place.
- Domain models and migrations already exist for users, properties, and interactions.
- Admin registration already exists for the major models.
- The custom user model, 2FA token model, active session model, property domain, favorites, inquiries, viewings, booking, payment, notification, search history, and activity log schemas are already present.
- Settings are already configured for Django templates, MySQL, a custom auth model, and console email.

What is not in place yet:
- There are only minimal core HTTP endpoints today.
- The current root page is a JSON response, not a real user interface.
- Registration, login, 2FA verification, logout, browse pages, detail pages, forms, and business workflows are not implemented yet.
- Existing tests currently cover only configuration and basic error-handler behavior, not the product flows.

This baseline matters because later ticket status marking must distinguish between schema or admin setup that already exists and user-facing behavior that still needs to be built.

## Agreed Technical Decisions

- Use Django auth patterns with the existing custom user model.
- Use email 2FA at login only.
- Do not require separate signup email verification in the MVP.
- When a new login succeeds, invalidate the prior active session for that user.
- Use Django's console email backend for the MVP.
- Keep admin management in Django admin for the full project scope currently planned.
- Keep supervisor reporting read-only and post-MVP.
- Treat booking as rental-only and post-MVP.
- Add simulated payments only after booking exists.
- Keep user-facing activity and history pages post-MVP.
- Keep recommendations and similar-listing alerts post-MVP.

## Planned Interfaces And Flows

### Registration Page / Form
- Actor: guest visitor.
- Input: email, password, and any optional minimal profile fields exposed by the form.
- Result: user account is created and the user can proceed to login.
- Permission rule: available only to unauthenticated visitors.
- Notable behavior: duplicate email must be rejected.

### Login Page / Form
- Actor: registered user.
- Input: email and password.
- Result: credentials are validated and a 2FA token is generated and delivered through the MVP email mechanism.
- Permission rule: available to unauthenticated users.
- Notable behavior: successful password validation does not complete login until 2FA succeeds.

### 2FA Verification Page / Form
- Actor: user who has passed the password step.
- Input: email token.
- Result: active session is created and prior active session for that user is invalidated.
- Permission rule: available only to a user in a pending-login state.
- Notable behavior: expired, invalid, or already used tokens must fail verification.

### Logout Action
- Actor: authenticated user.
- Input: logout request.
- Result: authenticated session ends.
- Permission rule: authenticated users only.
- Notable behavior: active session tracking must remain consistent after logout.

### Property Listing Page With Filters
- Actor: guest visitor or authenticated user.
- Input: filter values such as location, price range, category, bedrooms, and amenities.
- Result: server-rendered list of matching active properties.
- Permission rule: public read access.
- Notable behavior: removed listings are excluded from public browse results.

### Property Detail Page
- Actor: guest visitor or authenticated user.
- Input: property identifier.
- Result: server-rendered detail page for one visible property.
- Permission rule: public read access for visible listings.
- Notable behavior: unavailable properties remain readable but must be clearly marked unavailable, while removed listings are not public.

### Favorite / Unfavorite Action
- Actor: authenticated user.
- Input: property identifier.
- Result: property is added to or removed from the user's favorites.
- Permission rule: authenticated users only.
- Notable behavior: duplicate favorites are rejected or treated as idempotent.

### Inquiry Form Submission
- Actor: authenticated user.
- Input: property identifier and inquiry message.
- Result: inquiry is stored, status starts as open, interaction is logged, and confirmation email is generated.
- Permission rule: authenticated users only.
- Notable behavior: inquiry applies to all property categories.

### Viewing Request Form Submission
- Actor: authenticated user.
- Input: property identifier, requested datetime, and optional note.
- Result: viewing request is stored as pending, interaction is logged, and confirmation email is generated.
- Permission rule: authenticated users only.
- Notable behavior: requested datetime must be a valid future datetime.

### Admin CRUD And Interaction Review
- Actor: admin.
- Input: Django admin forms for properties, inquiries, and viewing requests.
- Result: listings and interaction records are created, updated, and reviewed through Django admin.
- Permission rule: admin users only.
- Notable behavior: MVP staff operations stay inside Django admin rather than a custom back-office UI.

## Data And Domain Notes

### Current MVP-Active Domain Models
- `User`: custom auth user using email as the unique identifier.
- `LoginTwoFactorToken`: stores hashed login 2FA tokens and verification state.
- `ActiveSession`: stores one current session record per user.
- `Property`: listing record with category, status, location, price, room counts, and owner linkage.
- `Amenity`: normalized amenity names.
- `PropertyImage`: image URLs for property detail display.
- `UserFavorite`: user-to-property saved listing relation.
- `PropertyInquiry`: persisted inquiry messages and their lifecycle status.
- `ViewingRequest`: persisted viewing requests and statuses.
- `SearchHistory`: stored search activity to support later reporting.
- `ActivityLog`: stored audit-style events for auth, interaction, transaction, and system scope.
- `EmailNotification`: persisted email notification metadata.

### Post-MVP Models Already Present In The Codebase
- `BookingRequest`: schema exists now, but the user-facing rental booking flow is post-MVP.
- `Payment`: schema exists now, but simulated payments are post-MVP and only follow booking.
- `ListingAlertSubscription`: schema exists now, but similar-listing alerts are post-MVP.

Rule for later ticketing:
- if a schema exists in the codebase but the product flow is deferred, the ticketing must treat the data baseline as present while still marking the actual feature as not implemented

## Page And UI Shape

Planned MVP page set:
- public landing or property discovery entry page
- registration page
- login page
- 2FA verification page
- property list and search page
- property detail page
- favorites page
- inquiry submission flow
- viewing request submission flow
- post-submission confirmation states

Staff UI:
- admin uses Django admin only in the MVP
- no custom supervisor pages in the MVP

Post-MVP page additions:
- supervisor reporting pages
- user-facing activity and history pages
- rental booking pages
- simulated payment pages or flows if later implemented

## Logging, Email, And Retention

- The MVP records search history and activity events in backend tables.
- The MVP generates login 2FA and confirmation emails using the console email backend already configured in settings.
- A 3-month retention rule exists at the product level for logs and interactions, but cleanup automation is deferred.
- Real email delivery is a later enhancement and is not an MVP dependency.

## Testing Expectations

The minimum testing direction for later implementation is:
- model and migration coverage for baseline entities
- auth flow tests for registration, login, 2FA, and single-session behavior
- page and form tests for property browsing, favorites, inquiries, and viewings
- admin access tests for staff actions
- email-generation assertions using the console or fake backend

The MVP does not commit to:
- advanced analytics validation
- performance benchmarking
- recommendation algorithm testing
- payment gateway testing

## Public Interfaces To Lock In

- Server-rendered web pages are the primary user interface.
- Django admin is the primary admin interface.
- Supervisor reporting is read-only and post-MVP.
- JSON APIs may exist where useful, but the system is not API-first.
- Booking and payments are not part of the MVP public interface.
