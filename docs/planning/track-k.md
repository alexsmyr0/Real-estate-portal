# Track K

## Mission

Track K owns the backend-heavy property, staff, reporting, seed-data, and recommendation work. This track carries most of the catalog query logic and most of the non-user-facing business logic after the foundational schema is in place.

## Ownership Boundaries

- Own property catalog backend behavior, filtering, availability rules, and listing governance.
- Own catalog seed data, demo fixtures, and Django admin usability for listings and interaction management.
- Own supervisor reporting and recommendation backend work.
- Avoid taking ownership of the primary end-user frontend except where minimal read-only staff pages are part of the reporting scope.

## Tickets

### K-01: Property Catalog Domain Baseline
Priority: Critical
Phase: P0 Existing Baseline
Depends On: None
Impacts: durable property schema ownership, amenity and image relationships, listing status rules, and catalog admin baseline
Blocks: K-02; K-04; K-05; K-06; A-05; A-06; N-04; N-05

Deliverables:
- Keep `Property`, `Amenity`, `PropertyAmenity`, and `PropertyImage` aligned with the PRD and SDS.
- Preserve category, status, location, price, room-count, and image baseline behavior.
- Keep the property-domain admin registration stable enough for later CRUD enhancement.

Acceptance Criteria:
- The catalog schema supports residential, commercial, and rental listings.
- Property records can represent availability and removal states distinctly.
- Amenities and images remain attachable to properties through the existing domain model.

Verification gate:
- Property migrations and admin baseline remain stable and covered by tests where appropriate.

### K-02: Public Catalog Read Routes And Query Service
Priority: Critical
Phase: P1 MVP Foundation
Depends On: K-01
Impacts: public catalog routes, listing retrieval service layer, and visible property selection
Blocks: K-03; A-05; A-06

Deliverables:
- Implement public catalog route wiring and query helpers for visible properties.
- Return the data needed for server-rendered list and detail pages without exposing removed listings.
- Keep catalog-read logic reusable by both listing and detail views.

Acceptance Criteria:
- Public catalog routes can load visible property records from the database.
- Removed listings are excluded from public browse results.
- The read layer can support both list pages and property-detail retrieval.

Verification gate:
- View and service tests cover public catalog access and visibility filtering behavior.

### K-03: Search, Filter, And Pagination Backend
Priority: Critical
Phase: P1 MVP Foundation
Depends On: K-02
Impacts: catalog filtering, query composition, result paging, and search-input normalization
Blocks: A-05; K-08; K-09; K-11

Deliverables:
- Implement filtering by location, price range, category, bedrooms, and amenities.
- Lock location matching to case-insensitive substring matching on `city` and `area`.
- Lock amenity filtering to all-selected-amenities matching and pagination to 12 listings per page.

Acceptance Criteria:
- Users can combine supported filter inputs in one search request.
- The location filter matches against `city` and `area` using case-insensitive substring search.
- Selected amenities use all-match semantics.
- Filter results are paginated at 12 listings per page.

Verification gate:
- Tests cover combined filters, fixed pagination behavior, and safe handling of invalid filter parameters.

### K-04: Property Detail Availability Rules And Listing Visibility
Priority: Critical
Phase: P1 MVP Foundation
Depends On: K-01
Impacts: detail-page visibility, unavailable-versus-removed behavior, and downstream booking or alert logic
Blocks: A-06; K-06; N-04; N-05; K-11

Deliverables:
- Define and implement backend rules for visible, unavailable, and removed listings.
- Support property detail retrieval for public-facing pages under those rules.
- Expose the availability context needed by user-facing catalog and post-MVP features.

Acceptance Criteria:
- Removed listings are not publicly retrievable.
- Unavailable listings remain readable but are clearly marked as unavailable.
- Detail retrieval follows a single consistent visibility policy across the site.

Verification gate:
- Tests cover visible, unavailable, and removed-listing access rules for detail retrieval.

### K-05: Demo Catalog Seed Data And Test Fixtures
Priority: High
Phase: P1 MVP Foundation
Depends On: K-01
Impacts: local development setup, realistic test data, and repeatable demo catalog states
Blocks: K-08; K-09; K-10; K-11

Deliverables:
- Add repeatable seed data or fixtures for representative residential, commercial, and rental listings.
- Include useful amenity, image, availability, and price-range variation for tests and demos.
- Make the seeded dataset usable for later reporting and recommendation verification.

Acceptance Criteria:
- Developers can load a representative catalog dataset without manual record creation.
- Seed data includes available, unavailable, and removed-listing examples.
- The seeded dataset supports reporting and recommendation test cases later in the roadmap.

Verification gate:
- Fixture or management-command tests prove the seed data loads cleanly and produces the expected baseline counts.

### K-06: Admin Listing CRUD
Priority: High
Phase: P2 MVP Completion
Depends On: K-01; K-04
Impacts: Django admin usability for creating and updating listings
Blocks: None

Deliverables:
- Improve Django admin configuration for properties, amenities, and images.
- Add practical list displays, search fields, filters, and edit support for MVP listing workflows.
- Keep admin-side management aligned with catalog visibility and status rules.

Acceptance Criteria:
- Admin can create and update listings through Django admin with practical field visibility.
- Listing-management views expose useful list filtering and search behavior.
- Listing status changes respect the agreed visible, unavailable, and removed rules.

Verification gate:
- Admin tests or manual verification scripts prove listing CRUD workflows are usable.

### K-07: Interaction Management Admin
Priority: High
Phase: P2 MVP Completion
Depends On: K-05
Impacts: Django admin usability for inquiries and viewing requests
Blocks: None

Deliverables:
- Improve Django admin configuration for inquiries and viewing requests.
- Add list displays, filters, search fields, and status-editing support for MVP interaction workflows.
- Keep interaction-management views practical for daily staff handling.

Acceptance Criteria:
- Admin can review and manage inquiries through Django admin.
- Admin can review and manage viewing requests through Django admin.
- Staff-management views expose useful filtering and search behavior for incoming user activity.

Verification gate:
- Admin tests or manual verification scripts prove inquiry and viewing management workflows are usable.

### K-08: Supervisor Inquiry And Saved-Property Reporting Aggregations
Priority: Medium
Phase: P3 Post-MVP Expansion
Depends On: N-03; K-05
Impacts: monthly inquiry counts, saved-property counts, and reusable reporting metrics services
Blocks: K-10

Deliverables:
- Build monthly aggregation logic for inquiries and saved properties.
- Provide reusable reporting data services for later read-only report pages.
- Keep aggregation logic consistent across different reporting periods.

Acceptance Criteria:
- Reporting services can compute monthly inquiry volume and favorite activity.
- Reporting data can be filtered by reporting period without changing business logic.
- Aggregation logic works against seeded and logged data sets.

Verification gate:
- Tests cover monthly aggregation output for inquiry and saved-property metrics against seeded reporting data.

### K-09: Search Trends Aggregation Service
Priority: Medium
Phase: P3 Post-MVP Expansion
Depends On: K-03; N-03; K-05
Impacts: monthly search-trend computation and reusable reporting trend services
Blocks: K-10

Deliverables:
- Build search-trend aggregation logic for cities, categories, and price bands.
- Return the top 10 searched cities, top 10 searched categories, and top 10 searched price bands per month.
- Lock price bands to `<100k`, `100k-249,999`, `250k-499,999`, `500k-999,999`, and `1,000,000+`.

Acceptance Criteria:
- Search-trend aggregation uses logged search data rather than ad hoc guesses.
- Trend output returns the locked top-10 sets for cities, categories, and price bands.
- Aggregation logic is consistent with the catalog filter semantics defined in K-03.

Verification gate:
- Tests cover trend calculations and price-band aggregation against seeded reporting data.

### K-10: Supervisor Reporting Read-Only Pages
Priority: Medium
Phase: P3 Post-MVP Expansion
Depends On: K-08; K-09
Impacts: read-only supervisor reporting UI and role-gated report access
Blocks: None

Deliverables:
- Build simple server-rendered reporting pages for supervisors and admins.
- Present monthly summary data through tables and lightweight report views.
- Keep reporting pages read-only and separate from listing-management workflows.

Acceptance Criteria:
- Supervisor users can access reporting pages without receiving edit controls.
- Report pages render inquiry counts, saved-property counts, and search-trend summaries.
- Reporting access stays restricted to authorized staff roles.

Verification gate:
- Page and permission tests cover authorized and unauthorized report access.

### K-11: Personalized Recommendations Backend
Priority: Medium
Phase: P3 Post-MVP Expansion
Depends On: K-03; K-04; N-03; K-05
Impacts: rule-based recommendation generation using catalog similarity and user behavior signals
Blocks: A-13

Deliverables:
- Implement a rule-based recommendation service without external ML dependencies.
- Require category match first, then rank by same-city preference, same price-band preference, amenity overlap, and recent favorites or search-history signals.
- Return the top 6 visible recommendation candidates per request surface.

Acceptance Criteria:
- The system can generate recommendation candidates without a separate recommendation engine.
- Recommendation logic uses stored user and catalog signals instead of manual curation.
- Results stay aligned with catalog visibility rules and return at most 6 visible listings.

Verification gate:
- Service tests cover recommendation generation for representative user-behavior patterns and ranking order.
