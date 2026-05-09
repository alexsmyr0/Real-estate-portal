**Ticket:** A-09 Viewing Request Flow End-To-End
**Branch:** `nikos/a-09`

## Final Verdict
**90 / 100** — Mergeable after addressing the minor scope and naming issues below. Implementation matches the A-09 deliverables exactly, all acceptance criteria are demonstrably covered, and the verification gate is satisfied by 10 passing tests with strong edge-case discipline.

### What was implemented
- [src/homefinder/apps/properties/forms.py](src/homefinder/apps/properties/forms.py) — `ViewingRequestForm` with `datetime-local` widget, future-datetime validation, and 500-char optional note.
- [src/homefinder/apps/properties/views.py:221](src/homefinder/apps/properties/views.py:221) — `viewing_request_action` (POST-only) with auth gate, visibility gate, form-level + service-level validation, session-marker confirmation, and isolated activity logging.
- [src/homefinder/apps/properties/urls.py:10](src/homefinder/apps/properties/urls.py:10) — `site-viewing-request` route under `/catalog/<id>/viewing-request/`.
- [src/homefinder/apps/interactions/services.py:340](src/homefinder/apps/interactions/services.py:340) — `create_viewing_request` service that persists, sends N-02 confirmation through `notification_service.send_viewing_confirmation`, and runs the email send inside `transaction.atomic()`.
- [templates/properties/detail.html:79](templates/properties/detail.html:79) — viewing request panel with auth gate for guests, form for authenticated users, one-shot success card.
- [tests/test_viewing_request_flow.py](tests/test_viewing_request_flow.py) — 10-test flow suite covering golden path, auth, datetime invariants, visibility, notification failure, and logging failure isolation.

### Acceptance criteria check
| Criterion | Status | Evidence |
|---|---|---|
| Authenticated user can submit valid future datetime | PASS | `test_authenticated_user_can_submit_future_viewing_request_and_get_verified_confirmation` |
| Successful request persists + triggers viewing confirmation email | PASS | Asserts `ViewingRequest`, `EmailNotification` with `VIEWING_CONFIRMATION` purpose and `SENT` status |
| Invalid requests receive clear validation feedback | PASS | `test_invalid_viewing_datetimes_return_clear_feedback_without_persistence` covers missing, malformed, past, and now-equal datetimes |
| Reuses N-02 notification service, not reimplemented | PASS | `notification_service.send_viewing_confirmation` is called from `create_viewing_request` |
| Compatible with N-03 logging without making it a hard blocker | PASS | `_safe_log_viewing_action` swallows logger errors; `test_logging_failure_does_not_break_viewing_persistence_or_notification` verifies isolation |

## Out of scope
### 1. Unrelated test fixes bundled in the PR
- [tests/interactions/test_log_retention.py:106](tests/interactions/test_log_retention.py:106) — switches the booking fixture to a rental property because `BookingRequest.clean()` enforces rental-only (an N-05 invariant). This is a pre-existing test bug fix, not A-09 work.
- [tests/interactions/test_similar_listing_alerts.py:335](tests/interactions/test_similar_listing_alerts.py:335) — replaces `order_by("-created_at")` with `order_by("-pk")`. Looks like a flake fix for tests that may share a created_at second.

**Why it matters:** A-09 is supposed to deliver the viewing flow only. Bundling test-suite hygiene fixes here makes the PR harder to review and conflates risk surfaces. If those tests were failing on `nikos/a-09` before A-09 work began, they should be a separate hotfix PR.

**Required fix (recommendation):** Split these two changes into a separate PR titled something like "fix: stabilize log-retention and alert tests". Do not block on this if the team prefers a single rollup, but call it out in the PR description so the reviewer sees the divergence.

## Blocking Findings
None. Implementation is functionally complete and verifiably correct.

## Testing gaps
No required gap. Coverage is unusually thorough for a single-ticket PR — auth gating, future-datetime validation across four invalid shapes, visible-but-unavailable property allowance, removed-property 404, one-time confirmation (forged query string is explicitly rejected), notification delivery failure marked as `FAILED`, and logging failure isolated from persistence.

Two soft suggestions, not gaps:
- No test for **note > 500 chars** path through the service. The form widget caps it at 500 via `maxlength`, but `create_viewing_request` enforces it server-side and that branch is currently untested. A direct service-level test would cement the contract.
- No test for **other-user data isolation** on the confirmation marker (e.g., user A submits, user B logs in on the same browser, opens the detail page, sees nothing). The session-key/`user=request.user` filter at [views.py:339](src/homefinder/apps/properties/views.py:339) already enforces this, but a regression test would harden it.

## Required Path To Pass
Optional polish before merge — none of these are blocking, but a stricter review would call them out:

1. **Rename misleading test.** [tests/test_viewing_request_flow.py:220](tests/test_viewing_request_flow.py:220) — `test_existing_viewing_request_remains_saveable_after_property_is_removed` mostly asserts that POSTing to a removed property returns 404. The "saveable" wording suggests a model-level persistence assertion that the test does not actually focus on. Consider `test_removed_property_blocks_new_viewing_requests_but_preserves_existing_records`.

2. **Drop the redundant `Property.objects.get`.** [views.py:248](src/homefinder/apps/properties/views.py:248) — `get_visible_property_detail(property_id)` already runs a query and is followed by `Property.objects.get(pk=property_id)`. Either return the model from the visibility helper or pass the id and resolve once inside `create_viewing_request`. Two queries where one suffices.

3. **Don't bare-`except Exception` without breadcrumbs.** [views.py:395](src/homefinder/apps/properties/views.py:395) and [views.py:411](src/homefinder/apps/properties/views.py:411) — `_safe_log_favorite_action` and `_safe_log_viewing_action` swallow every exception silently. The N-03 contract is already supposed to be no-op-safe, so this wrapper is double-defensive. If you keep it, at least `logger.exception(...)` so a production logger outage is visible. As written, a real bug in the activity logger becomes invisible.

4. **Service-layer validation duplicates form validation.** [services.py:348-371](src/homefinder/apps/interactions/services.py:348) re-checks auth, future datetime, note length, and visibility, all of which are already enforced upstream by the view (`_require_authenticated_user`, `get_visible_property_detail`, `ViewingRequestForm.clean_requested_datetime`). It is reasonable defense-in-depth for a service that other callers may eventually use, but if `create_viewing_request` is only ever called from this view, the duplication is overbuilt for current scope. Acceptable either way — flag for the team to decide intent.

5. **CSS additions are scoped and minimal** ([shared-shell.css:548-685](src/homefinder/apps/core/static/core/css/shared-shell.css:548)). No concerns. Reuses the existing form-grid and panel system.
