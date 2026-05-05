**Ticket:** A-03: Shared Site Shell, Navigation, And Base Template System
**Branch:** `alex/a-03`

## Final Verdict
84/100

Strong enough to merge if team accepts the temporary `site/` URL namespace, but not a clean full-credit A-03. The base template, navigation partial, flash-message partial, form layout, property card, empty state, shared CSS, and page coverage exist and pass tests. Main deductions are route/product clarity and scope discipline.

## Out of scope
### 1. `site/catalog/` starts implementing public catalog UI before A-05
**Why it matters:**
A-03 should provide shell and reusable primitives. A-05 owns the public landing/catalog frontend, including catalog template, filter controls, property cards, pagination controls, and empty-state behavior. This branch adds a real `/site/catalog/` page using `parse_catalog_search_params()` and `search_visible_properties()`, which makes the shell ticket partly own catalog presentation.
**Required fix:**
Remove. A5 will handle it.

### 2. Navigation copy is scaffold/demo copy, not product navigation
**Why it matters:**
Every future page extending `base.html` inherits nav labels like `Shell Home`, `Catalog Shell`, and `Sign In (A-04)`. That is useful for proving A-03, but it is not a stable browser-facing HomeFinder shell.
**Required fix:**
Use product-facing labels and stable target names, or clearly isolate A-03 demo pages from final shared navigation.

## Testing gaps
### 1. Responsive requirement is not directly tested
The ticket explicitly requires usability down to 375px width. CSS has media queries at 920px and 620px, but tests only assert server-rendered HTML/templates. No visual/browser regression checks prove the 375px state.

### 2. Empty catalog shell state is under-tested
The empty-state partial renders, but the template still renders pagination text using `pagination.page` and `pagination.total_pages`, which can produce awkward states like `Page 1 of 0` when no listings exist.

### 3. Raw `unittest discover` still fails in this repo environment
`./.venv/bin/python -m unittest discover -s tests` bypasses the repo's Django test runner/settings and tries to use default MySQL, which is unavailable in this audit environment. `manage.py test` is the valid repo gate and passes.

## Required Path To Pass
1. make `/` the shell home and reserve `/catalog/` for A-05
2. Replace scaffold nav copy with product-facing labels, or keep demo-only shell pages out of inherited production navigation.
3. Add a small test or browser smoke check for 375px responsive shell behavior.
4. Hide or normalize pagination on empty catalog shell results so it never displays impossible page counts.

Verification run:
- `./.venv/bin/python manage.py check` passed.
- `./.venv/bin/python manage.py test tests.test_site_shell` passed: 5 tests.
- `./.venv/bin/python manage.py test` passed: 70 tests.
- `./.venv/bin/python manage.py makemigrations --check --dry-run` passed with no changes detected; local MySQL warning only.
