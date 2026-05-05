**Ticket:** A-03: Shared Site Shell, Navigation, And Base Template System
**Branch:** `alex/a-03`
**Re-audit commit:** `98fed94` ("fixed") — reassessment after v1 required fixes

## Final Verdict
91/100 — Pass

All four required-path items from the v1 audit are resolved. The shell is at `/`, catalog is gone, navigation uses product labels, 375px CSS exists and is tested. Remaining deductions are minor test quality issues and one latent template bug that will bite A-05 if not caught first.

## Previous Required Fixes — Status

### 1. `/site/catalog/` removed ✓
`site_catalog` view and template deleted. URL removed from `urls.py`. Test confirms `/site/catalog/` → 404. `parse_catalog_search_params()` and `search_visible_properties()` imports gone from `views.py`.

### 2. Navigation copy replaced with product labels ✓
`Shell Home` → `Home` (active link), `Catalog Shell` → `Browse Listings` (disabled `<span>`), `My Activity` added as disabled `<span>`. `Sign In (A-04)` → `Sign in`. Labels are stable product-facing names. Disabled spans carry `aria-disabled="true"` and `nav-link-disabled` CSS class.

### 3. Shell home moved to `/` ✓
`path("", views.site_home, name="home")` in `core/urls.py`. All `{% url 'site-home' %}` and `{% url 'site-catalog' %}` references removed from templates. `_navigation.html` resolves `home_url` cleanly.

### 4. 375px responsive CSS added and tested ✓
Media query at `max-width: 375px` added to `shared-shell.css` (line 465). Covers `.site-shell`, `.site-header`, `.brand`, `.site-nav`, `.nav-auth`, `.button`. Test `test_css_contains_375px_responsive_shell_rules` verifies query block exists.

### 5. Pagination impossible-state eliminated ✓
Entire catalog view and template gone. No pagination context ever reaches a template. Empty-state pagination bug (Page 1 of 0) cannot occur.

---

## New Issues Found

### 1. CSS responsive test assertions are too loose — testing gap (low)
`test_css_contains_375px_responsive_shell_rules` checks:
```python
self.assertIn("@media (max-width: 375px)", css)
self.assertIn(".site-nav,", css)
self.assertIn(".nav-auth {", css)
self.assertIn(".button {", css)
```
`.nav-auth {` and `.button {` match at lines 98 and 271 respectively — both exist **outside** the 375px block. The test would pass even if the 375px block's internal rules were deleted, as long as those selectors remain elsewhere in the file. Only the first assertion meaningfully proves the 375px block exists.

**Impact:** Low for A-03. The rules are currently there. But the test gives false confidence that the responsive rules are inside the media query.
**Suggested fix:** Slice the CSS string between `@media (max-width: 375px)` and its closing brace and assert within that substring.

### 2. `_property_card.html` bathroom pluralization breaks with real ORM objects — latent bug (medium, hits A-05)
`templates/partials/_property_card.html` line 20:
```html
{% if property.bathrooms != '1.0' %}s{% endif %}
```
The demo dict in `site_home` passes `"bathrooms": "1.5"` (string), so `"1.5" != '1.0'` → `True` → "baths" renders correctly.

When A-05 passes a real `Property` ORM object, `bathrooms` is a `Decimal` field. In Python:
```python
>>> from decimal import Decimal
>>> Decimal("1.0") != '1.0'
True
```
Cross-type comparison is always `True`, meaning a property with exactly 1 bathroom will render "1.0 baths" instead of "1.0 bath". Pluralization is always wrong for 1-bathroom listings.

**Impact:** Silent rendering bug, not a crash. Will affect every single-bathroom property card once A-05 wires real data.
**Suggested fix:** Change comparison to `{% if property.bathrooms != 1 %}` (integer literal) or use a Django template filter.

### 3. Demo form submits but is never processed — informational (low)
`ShellContactPreferenceForm` has `full_name`, `email`, `intent` all `required=True`. The form renders with `form_method="get"` submitting to `/`. The `site_home` view always constructs a fresh unbound form, ignoring GET params entirely. Submitting the form reloads the page with query params in the URL but no validation feedback, no success state.

**Impact:** Not a bug for A-03 shell scope — this is a layout primitive demo, not a functional form. No data is lost or corrupted. But the form looks functional (has required fields, submit button) and silently does nothing, which could mislead the next developer extending this view.
**No required fix for A-03.** Acceptable as-is given the demo context.

### 4. `index` view relocated to `/api/v1/` — informational (no action needed)
`path("api/v1/", views.index, name="index")` replaces the old `path("", views.index, ...)`. The JSON status endpoint `{"status": "ok", "service": "homefinder"}` is now at `/api/v1/` instead of `/`. No code references `reverse('index')`. Future API routes registered at root with `path("", include(...))` will not conflict. Clean.

---

## Verification Run

- `./.venv/bin/python manage.py check` → passed, 0 issues.
- `./.venv/bin/python manage.py test tests.test_site_shell` → passed: 5 tests in 0.028s.
- `./.venv/bin/python manage.py test` → passed: 70 tests in 0.394s.
- `./.venv/bin/python manage.py makemigrations --check --dry-run` → no changes detected; local MySQL warning only.
