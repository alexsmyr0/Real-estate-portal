# Track Admin

## Mission

Track Admin delivers the Admin actor use cases through a purpose-built in-app section so the SRS use case diagram, SDS class and sequence diagrams, and source code all map to one another. The scenario explicitly lists *"Admins can add and update property listings and manage user interactions"* as a functional requirement, but the current implementation routes the Admin actor into Django's framework-generated `/admin/` site, which has no corresponding artifact in the SRS or SDS. That breaks the design-to-implementation mapping the Phase 2 and Phase 3 rubric bands assess. This track closes that gap with the smallest set of artifacts that lets the demo showcase the Admin actor in pages the team designed.

## Ownership Boundaries

- Own the custom in-app admin section under `/staff/listings/...` and any sibling admin routes added for the Admin actor.
- Own the access-control gate that distinguishes the Admin role from Supervisor and User roles.
- Own the design and documentation artifacts that map the Admin actor use cases to the implemented views.
- Reuse the existing site shell, navigation partials, form styling, and base templates owned by Track A rather than introducing a parallel design system.
- Reuse the existing property, inquiry, viewing, and booking models, services, and validation rules owned by Tracks K and N rather than duplicating business logic.
- Do not remove or replace the Django admin site, which Track K still maintains as a developer-facing tool.

## Tickets

### AD-01: Admin Role Access Control Decorator
Priority: Critical
Phase: P4 Final Expansion And Hardening
Depends On: A-01
Impacts: reusable role gate for admin-only views and consistent 403 behavior for non-admin users
Blocks: AD-02; AD-03

Deliverables:
- Add an `admin_required` decorator (or matching helper) that authorizes only users whose `role` equals `UserRole.ADMIN`.
- Return a clear 403 response for authenticated non-admin users and route unauthenticated users through the standard login redirect.
- Keep the helper consistent in shape with the existing `_require_reporting_user` pattern used by the supervisor reports flow.

Acceptance Criteria:
- Calling the decorator on a placeholder view rejects guests, regular users, and supervisors while admitting admins.
- The helper raises or returns the same response type the rest of the staff section already uses, so downstream views do not need bespoke error handling.
- The decorator is importable from a stable module path so all Track Admin views can adopt it without copy-paste.

Non-goals:
- Do not change the existing supervisor reports permission helper.
- Do not introduce a new role or alter the `UserRole` enum.
- Do not build any admin pages or routes here.

Verification gate:
- Unit tests cover all four access cases (guest, user, supervisor, admin) against a throwaway view that uses the decorator.

### AD-02: Admin Listing CRUD End-To-End
Priority: Critical
Phase: P4 Final Expansion And Hardening
Depends On: AD-01; A-03; K-01; K-04; K-06
Impacts: in-app admin pages for listing list, create, edit, and delete; image and amenity inlines; admin navigation entry point
Blocks: AD-04

Deliverables:
- Add `staff/listings/`, `staff/listings/new/`, `staff/listings/<id>/edit/`, and `staff/listings/<id>/delete/` routes under the existing properties app URL config.
- Implement a `PropertyForm` `ModelForm` over `Property`, with `PropertyImage` and `PropertyAmenity` driven by Django inline formsets so a listing can be created with images and amenities in a single submission.
- Build `listing_list.html`, `listing_form.html`, and `listing_confirm_delete.html` templates extending the existing site shell so the look matches the supervisor reports pages.
- Add a "Listings" link to the authenticated staff navigation alongside the existing "Reports" link, visible only to admins.
- Apply the AD-01 decorator to every Track Admin view.
- Respect the locked visible, unavailable, and removed listing rules owned by K-04 when displaying or filtering admin list entries.

Acceptance Criteria:
- An authenticated admin can create a property with at least one image and at least one amenity in a single form submission.
- An authenticated admin can edit an existing property's fields, images, and amenities without losing previously attached records.
- An authenticated admin can delete a property after an explicit confirmation step.
- Non-admin requests to any `staff/listings/...` route return 403.
- The listing pages render through the shared site shell and reuse the existing form and table styling instead of introducing new visual primitives.

Non-goals:
- Do not replace the Django admin registration owned by K-06.
- Do not build catalog filtering, search, pagination, or recommendation logic here.
- Do not add user account management, role assignment, or password reset flows.
- Do not absorb inquiry, viewing, or booking management here (covered by AD-03).

Verification gate:
- Integration tests cover non-admin 403 rejection, admin create with a `PropertyImage` and a `PropertyAmenity` persisted through inline formsets, admin edit, admin delete, and at least one invalid-form validation path.

### AD-03: Admin User Interaction Management Pages
Priority: High
Phase: P4 Final Expansion And Hardening
Depends On: AD-01; A-03; A-08; A-09; N-05; K-07
Impacts: in-app admin pages for inquiries, viewing requests, and rental bookings; status update affordances; admin navigation
Blocks: AD-04

Deliverables:
- Add read-and-manage routes under the staff section for inquiries, viewing requests, and bookings, gated by the AD-01 decorator.
- Render lightweight list views for each interaction type with the existing site shell and a small detail or status-update affordance per row.
- Reuse the persistence, validation, and status vocabularies already owned by A-08, A-09, and N-05 instead of redefining interaction state machines.
- Add the admin navigation entries to the same staff nav slot introduced by AD-02 so the Admin actor has one obvious entry point per use case.

Acceptance Criteria:
- An authenticated admin can list inquiries, viewing requests, and rental bookings and see their current status.
- An authenticated admin can advance an interaction to its next valid status without bypassing the rules enforced by the owning track.
- Non-admin requests to any interaction-management route return 403.
- The pages render through the shared site shell and do not duplicate the table or form styling.

Non-goals:
- Do not change the underlying inquiry, viewing, or booking business rules owned by A-08, A-09, or N-05.
- Do not implement messaging, broadcast notifications, or bulk action workflows.
- Do not replace the Django admin registrations owned by K-07.
- Do not add payment management UI here (Track N owns the simulated payment surface through N-06 and A-14).

Verification gate:
- Integration tests cover non-admin 403 rejection, admin list rendering for at least one populated interaction type, and at least one status update transition persisted through the admin page flow.

### AD-04: Admin Surface Documentation And Design Mapping
Priority: High
Phase: P4 Final Expansion And Hardening
Depends On: AD-02; AD-03
Impacts: SRS use case diagram, SDS class diagram, SDS sequence diagram, and SRS/SDS textual sections that reference the Admin actor
Blocks: None

Deliverables:
- Update the SRS use case diagram so the Admin actor connects to the implemented admin views rather than the Django admin site.
- Update the SDS class diagram to include the admin views, the `PropertyForm` `ModelForm`, and the inline formset relationships introduced by AD-02 plus the interaction-management views introduced by AD-03.
- Add or update at least one SDS sequence diagram for the admin create-listing flow so the design-to-code mapping is explicit.
- Update SRS and SDS textual sections that previously implied Django admin satisfied the Admin actor use cases.
- Keep documentation aligned with the implemented routes, decorators, forms, and templates so a marker can trace any element on a diagram to a file in source control.

Acceptance Criteria:
- The use case diagram shows the Admin actor reaching the in-app admin views, not the Django admin URL.
- The SDS class diagram shows the AD-02 and AD-03 view classes or functions, the `PropertyForm`, and the inline formset relationships.
- At least one sequence diagram traces the admin create-listing path from the navigation entry point to the persisted property record.
- SRS and SDS prose reflects the new admin section without contradicting the implemented behavior.

Non-goals:
- Do not add new code paths, routes, or views here.
- Do not redesign the existing supervisor reports flow or its diagrams.
- Do not produce a separate developer-onboarding document.

Verification gate:
- A short cross-check confirms that every element added to the diagrams maps to a file or symbol present in source control after AD-02 and AD-03 land.
