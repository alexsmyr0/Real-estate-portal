**Ticket:** A-08 Inquiry Flow End-To-End
**Branch:** `nikos/a-08`

## Final Verdict
95 / 100

A-08 now passes. After the merge with `main` and the follow-up cleanup commit `461b64e` ("Clean up A-08 inquiry flow scope"), every "Required Path to Pass" item from the prior audit was addressed and the three flagged testing gaps were closed. The implementation is leaner, the scope drift is gone, and the architecture matches A-09's pattern (separate POST endpoint, GET-only detail page). Tests cover all the behavior the ticket's verification gate asks for and also lock in the edge cases I asked for — favorite-state preservation, the unsaved `Property(id=...)` shape, and the exact `next=` redirect target.

## Out of scope

None. The earlier "out of scope" calls were:

1. **Retention-test edit** — reconciled. A-09 made the identical fix on `main` (the `BookingRequest` start/end_date requirement is a real upstream change). The current branch correctly takes main's version.
2. **`.detail-hero` mobile CSS rule** — reverted in `461b64e`.

## Blocking Findings

None.

## Testing gaps

None of substance. The 18 tests in `tests/interactions/test_property_inquiry_flow.py` cover:

- Auth gating (anonymous GET shows the sign-in panel; anonymous POST redirects to login with `next=` pointed at the detail URL — exact-match asserted).
- Valid submission persists the inquiry, sends the confirmation email through the console backend (stdout-asserted), and writes the `inquiry_submitted` activity log with the right details.
- Validation: missing message, overlong message (preserves user input), and service-level rejection of removed/invalid property IDs.
- Visibility: removed properties 404 on both GET and POST; unavailable properties still accept inquiries.
- Side-effect safety: logging-failure no-op safety and notification-delivery failure each leave exactly one inquiry plus the appropriate notification record.
- Cross-flow: catalog cards still link to the detail page, the existing favorite state is preserved on the detail page after the inquiry section was added, and the service accepts the unsaved `Property(id=...)` shape that the view passes through.

## Required Path To Pass

None blocking. Two minor nits, neither worth holding the merge for:

1. **The `from django import forms` import in `properties/views.py`** is only consumed by the type annotation on `_add_validation_error_to_form`. With `from __future__ import annotations` in effect the annotation is lazy, so the import is technically unused at runtime. Either keep it for IDE/typing benefit (current state) or drop it and switch the annotation to a string. Either is fine.

2. **`logger = logging.getLogger(__name__)` in `properties/views.py`** is not used by any A-08-introduced code path; it's a holdover from A-09's `_safe_log_viewing_action`. Already on main; not A-08's problem.

## Summary of what changed since the last audit

| Prior finding | Resolution |
| --- | --- |
| `PropertyInquiry.clean()` + `save()` overrides duplicated service validation and forced hidden DB lookups on every save | Removed entirely. Validation lives only in the service. |
| `StyledInteractionFormMixin` was a single-use abstraction | Inlined into `PropertyInquiryForm.__init__`. |
| Session marker + `PropertyInquiry.objects.filter().exists()` roundtrip on every detail-page GET to gate the confirmation banner | Removed. Success state is now a one-shot `messages.success()` flash, consistent with the rest of the site. |
| Inquiry POST inlined into `property_detail_page`, conflicting with A-09's GET-only detail-page pattern | Split into a dedicated `submit_inquiry_action` view at `/catalog/<id>/inquiry/`, mirroring `viewing_request_action`. |
| Unrelated retention-test and `.detail-hero` CSS edits | Retention test resolved via main; `.detail-hero` reverted. |
| No regression test for favorites after inquiry section added | `test_detail_page_preserves_existing_favorite_state_with_inquiry_section` added. |
| No service test for unsaved `Property(id=...)` shape | `test_service_accepts_unsaved_property_id_shape_for_available_property` added. |
| `next=` redirect target asserted only by prefix | Now exact-equality against `f"{login_url}?{urlencode({'next': detail_url})}"`. |

A-08 is ready to merge.
