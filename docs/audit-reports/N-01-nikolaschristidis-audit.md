# PR Audit — N-01 (Track N) — `funcs-for-properties-and-listings/nikolaschristidis`

**Author:** nikolaschristidis  
**Reviewer:** Steven  
**Branch base:** `origin/main` @ `9b03e63`  
**Branch head:** `1074815 Strengthen N-01 schema baseline guards`  
**Verdict:** Conditionally Acceptable — useful guard tests, but the ticket was already implemented, the scope is partly redundant, and there is one packaging bug that can break test discovery.

---

## TL;DR

- **Was N-01 already implemented before? Yes — fully.** Every model, every field, every `db_table`, every migration, and every `admin.site.register(...)` listed in the N-01 deliverables already lived on `main` at `9b03e63`. The ticket-tracker also marks `N-01` as `[x]` Done. Nikolas did not add or change any model, migration, or admin code — his diff is *only* a new test file (+281 lines) and two `.gitignore` entries.
- **What he actually did:** wrote characterisation/regression tests that *pin* the existing N-01 schema and admin wiring against future drift. That is a legitimate, in-scope contribution to the verification gate ("Migrations and admin wiring remain stable"), just not a new "implementation".
- **One real bug:** he forgot `tests/interactions/__init__.py`, which breaks `python manage.py test tests.interactions...` and `python -m unittest tests.interactions...` (the two commands the repo's own `pr-audit` workflow lists). Empirically reproduced.

---

## Scope check vs `track-n.md` § N-01

| N-01 requirement | Status in this PR |
|---|---|
| Keep N-01 models aligned with PRD/SDS | Untouched on this branch — already aligned on `main` |
| Preserve baseline admin registration | Untouched on this branch — already wired on `main` |
| Keep deferred post-MVP schemas present without claiming completion | Honored — no feature code added |
| Verification gate: migrations + admin remain stable | Partially addressed via new tests |

**Non-goals** (delivery logic, logging service, alert/booking/payment flows): all respected. No scope creep into N-02/N-03/N-04/N-05/N-06.

---

## Files changed

```
.gitignore                                 |   2 +
tests/interactions/test_schema_baseline.py | 281 +++++++++++++++++++++++++++++
```

Two commits, both Nikolas, both on-topic:

- `a9f7eaf` Add N-01 schema baseline tests
- `1074815` Strengthen N-01 schema baseline guards (upgrades `SimpleTestCase` → `TestCase`, adds DB-introspection check + per-field contract tests)

---

## What's good

- Tests are thorough at the *attribute* level: locked `db_table`, field types, `max_length`, `max_digits`/`decimal_places`, `choices`, defaults, FK `on_delete`, `null`, `blank`. Future drift on these will fail loudly.
- Coverage spans all six N-01 models plus the `ListingAlertSubscriptionAmenity` through-table.
- Helper methods (`assert_field_contract`, `assert_fk_contract`, `assert_model_has_fields`) are clean, reusable, and well-typed.
- Admin registration check uses `admin.site.is_registered(model)` — the right call.
- Non-goals respected: no service code, no view code, no migration edits.
- The follow-up commit ("Strengthen…") iterates on review-style feedback in the right direction (looser → stricter).

---

## Problems

### 1. Missing `tests/interactions/__init__.py`  *(real bug)*

The repo's existing convention (and the project's own `.agents/workflows/pr-audit.prompt.md`) calls `python manage.py test` and `python -m unittest discover -s tests`. I reproduced:

```
loader.discover(start_dir='tests/interactions', ...)
# ImportError: Start directory is not importable: 'tests/interactions'
```

Targeted invocations (`manage.py test tests.interactions.test_schema_baseline`) will fail outright; broad `discover -s tests` may silently skip the new file because `tests/interactions/` is treated as a non-package without an `__init__.py`. Add an empty `tests/interactions/__init__.py`. This is the single biggest issue in the PR.

> Note for cleanup: I created a temporary empty `tests/interactions/__init__.py` while reproducing the bug; the sandbox blocked deletion. You'll see it as untracked locally — `git clean -fd tests/interactions` removes it. (Or commit it as the fix.)

### 2. Promoting *every* test to `django.test.TestCase` is heavy-handed

Commit 2 moves the whole class from `SimpleTestCase` to `TestCase`. Only `test_n01_migrated_tables_exist_in_database` actually needs a DB. The other five tests are pure Python introspection of `_meta`. They now require a live MySQL connection (or a SQLite swap) just to assert that `EmailNotification.purpose.max_length == 24`. Either:

- Split into two classes (`SimpleTestCase` for metadata, `TestCase` for the introspection check), or
- Use `TransactionTestCase`/`SimpleTestCase` selectively per-method.

This matters because the team's MySQL container won't always be up locally; PR-audit reviewers will hit DB errors on tests that have no business needing one.

### 3. `test_n01_migrated_tables_exist_in_database` is mostly tautological

`Django TestCase` runs migrations into the test DB on setup, so asserting that the tables it just created exist isn't really verifying *our* migrations are correct — it's verifying Django works. Two stronger guards would replace this:

- `call_command("makemigrations", "--check", "--dry-run")` — fails if a model has drifted from migrations without one being generated. This is the *actual* "migrations remain stable" gate from the ticket.
- `call_command("migrate", "--plan", "--check")` to ensure no unapplied migrations.

These directly speak to the N-01 verification gate and don't need a populated DB.

### 4. Choice *values* are not locked, only choice *lists by reference*

He asserts e.g. `choices=EmailNotificationPurpose.choices`, which means "whatever the enum says today equals whatever the field is set to today." If a future dev renames `LOGIN_2FA` → `LOGIN_OTP` in the enum, both sides change together and the test still passes. Since the PRD/SDS pin specific notification *purposes* and activity *scopes*, the test should also pin the literal expected members:

```python
self.assertEqual(
    {c[0] for c in EmailNotificationPurpose.choices},
    {"LOGIN_2FA", "VIEWING_CONFIRMATION", "INQUIRY_CONFIRMATION",
     "BOOKING_UPDATE", "SIMILAR_LISTING_ALERT"},
)
```

Same for `ActivityScope`, `BookingRequestStatus`, `PaymentStatus`, `PaymentMethod`, `PaymentPurpose`. Without this, the "schema baseline" isn't really locked — the *names* of the contract are still freely renameable.

### 5. Missed gaps in coverage

- No assertion of the `uq_listing_alert_subscription_amenity` `UniqueConstraint`. That uniqueness constraint is part of the baseline.
- No assertion of `Meta.ordering` (`-created_at` etc.) — minor, but stated in models and arguably part of "baseline behavior."
- No assertion that `EmailNotification.user` and other nullable FKs use `SET_NULL` *and* have `related_name` set (related_name is currently checked nowhere; future renames to `email_notifications` related accessor would silently break callers).
- No test for the `Payment.booking_request` `SET_NULL` semantics actually behaving as expected when a booking is deleted (covered by Django, but again — we're claiming to lock the contract).

### 6. `.gitignore` additions are unrelated scope creep

Adding `.tmp/` and `.run-temp/` has nothing to do with N-01. It's harmless, but it shouldn't ride along in a "schema baseline guards" PR. Pull it into a chore commit/PR.

### 7. Minor style nits

- `self.assertLessEqual(expected_tables, migrated_tables)` for set subset — works (sets implement `<=` as `issubset`), but `assertTrue(expected_tables.issubset(migrated_tables))` is much clearer to a reader.
- `django.setup()` at module top level is consistent with `tests/test_error_handlers.py`, but if you ever switch to pytest-django this needs to come out.
- The class is a single ~280-line god-object. Splitting per-domain (notification / logging / alert / commerce) would make failures easier to read.

---

## Did he do anything stupid?

Two things, both small:

1. **Forgot `tests/interactions/__init__.py`.** This is the only thing I'd actually block the PR on. It silently breaks the project's own documented test commands.
2. **Upgraded the whole class to `TestCase` instead of splitting.** Couples five DB-free metadata checks to a live MySQL — annoying, and easy to fix.

The work itself is *not* stupid, but it is **redundant** as an "N-01 implementation": the ticket was already done, and this PR is really an N-01 *regression-test* PR. That framing would have made the scope clearer in commit messages and review.

---

## Was N-01 truly implemented before?

**Yes.** On `origin/main` at `9b03e63` (the merge base of this branch):

- `src/homefinder/apps/interactions/models.py` defines `EmailNotification`, `SearchHistory`, `ActivityLog`, `BookingRequest`, `Payment` with all baseline fields, `db_table` names, and `Meta.ordering`.
- `src/homefinder/apps/properties/models.py` defines `ListingAlertSubscription` (+ `ListingAlertSubscriptionAmenity` through-model with the unique constraint).
- `interactions/admin.py` and `properties/admin.py` register every one of these models with `admin.site.register(...)`.
- Migrations `0001_initial.py` / `0002_initial.py` in both apps create all the corresponding tables.
- `docs/planning/ticket-tracker.md` line 109: `[x] **N-01** P0 - Notification, Logging, Alerts, And Deferred-Commerce Schema Baseline ...`

Nikolas added zero code under `src/`. So your instinct was correct — N-01 was already in.

---

## Recommended actions before merge

1. Add `tests/interactions/__init__.py` (empty file). **Required.**
2. Either split the class so metadata-only tests stay on `SimpleTestCase`, or accept the DB requirement and document it. **Strongly recommended.**
3. Replace the "tables exist after migration" test with `makemigrations --check` and `migrate --check`. **Recommended — actually addresses the verification gate.**
4. Pin literal choice members for `EmailNotificationPurpose`, `ActivityScope`, and the booking/payment status enums. **Recommended.**
5. Move the `.gitignore` change to a chore PR. **Nice-to-have.**

**Grade: B−.** Useful and correctly scoped tests, but ships with a discovery-breaking omission, an over-broad base class, and one tautological test in place of the test that would actually satisfy the ticket's verification gate.
