---
description: Implement a specific ticket for the HomeFinder project.
---

# Implementation Workflow: {Ticket}

You are implementing exactly one ticket for **HomeFinder**, a Django-based real estate portal.

The project context is fixed:
- Django monolith
- MySQL
- server-rendered templates
- light JavaScript only where it improves UX
- Django admin for staff workflows
- no SPA architecture
- no separate frontend app

Your job is to implement the selected ticket cleanly, satisfy its verification gate, and avoid scope creep.

## 1. Read The Source Of Truth First

Before changing code, read:
- the workspace AGENTS instructions provided in the current execution environment
- `docs/planning/prd.md`
- `docs/planning/sds.md`
- `docs/planning/ticket-tracker.md`
- the owning track file:
  - `docs/planning/track-a.md`
  - `docs/planning/track-k.md`
  - `docs/planning/track-n.md`

Then locate the selected ticket and read all of it:
- `Priority`
- `Phase`
- `Depends On`
- `Blocks`
- `Deliverables`
- `Acceptance Criteria`
- `Non-goals`
- `Verification gate`

Do not start implementation until the ticket definition is fully understood.

## 2. Ticket Execution Rules

### 2.1 One Ticket Only
- Implement only the selected ticket.
- Do not silently absorb adjacent tickets just because the code is nearby.
- If you must make a tiny supporting change outside the ticket, keep it minimal and justify it.

### 2.2 Respect Dependencies
- Check `Depends On` in the track file and tracker before starting.
- If a required dependency is not implemented and the ticket cannot be completed honestly without it, stop and report the blocker.
- Do not bypass dependency order by quietly implementing major parts of another ticket.

### 2.3 Non-goals Are Binding
- Treat the ticket's `Non-goals` as hard boundaries.
- Do not add extra features, extra endpoints, extra UI, or refactors that belong to another ticket.
- If you notice a tempting improvement outside the ticket scope, note it separately instead of implementing it.

### 2.4 Verification Gate Is The Finish Line
- The ticket is not done until its verification gate is satisfied.
- Do not mark a ticket `[x]` if the verification gate is not actually met.
- Use `[-]` only when a meaningful subset exists but the ticket is still incomplete.

## 3. HomeFinder-Specific Implementation Guidance

### 3.1 Architecture And Implementation Style
- Keep implementation aligned with the PRD and SDS.
- Prefer Django-native patterns over inventing new architecture.
- Use Django templates, views, forms, models, and admin where appropriate.
- Use JavaScript sparingly for progressive enhancement, not for SPA-style application state.
- Keep MVP features fake where the planning docs say they are fake:
  - email uses console/fake delivery in MVP
  - payments are simulated only, and post-MVP

### 3.2 Likely Code Areas
Depending on the ticket, the main implementation area will usually be one or more of:
- `src/homefinder/apps/users/`
- `src/homefinder/apps/properties/`
- `src/homefinder/apps/interactions/`
- `src/homefinder/apps/core/`
- `templates/`
- app static assets under Django app `static/` directories or a shared `static/` area if introduced consistently
- `tests/`

### 3.3 Track Expectations
- Track `A`: user-facing pages, templates, CSS, most JS, and user-flow backend.
- Track `K`: catalog/search/admin/reporting/recommendation backend.
- Track `N`: notifications, logging, alerts, booking, payments, and retention or messaging operations.

Stay within the intended ownership shape unless a small supporting cross-track edit is necessary.

## 4. Practical Workflow

### Step 1: Confirm The Ticket Boundary
- Copy the selected ticket definition into your working context.
- Restate the ticket goal in one or two sentences.
- Identify what is explicitly in scope and explicitly out of scope from `Non-goals`.

### Step 2: Inspect The Existing Baseline
- Read the relevant models, views, admin, templates, settings, URLs, and tests before editing.
- Pay attention to current baseline behavior already present in the repo.
- If the ticket is a `P0 Existing Baseline` ticket, preserve and tighten what exists instead of rebuilding from scratch.

### Step 3: Implement The Smallest Complete Version
- Start with the minimum implementation that satisfies the deliverables and acceptance criteria.
- Prefer incremental, testable changes over broad refactors.
- When changing models, create or update migrations explicitly if needed.
- When changing UI, keep the shared layout and styling conventions consistent with the existing HomeFinder plan.

### Step 4: Verify Honestly
- Run the smallest relevant test set first.
- Then run broader verification if needed for confidence.
- If the ticket touches Django behavior, use Django-aware tests where appropriate.
- If the ticket touches templates or user flows, verify render paths and permissions as well as business logic.

### Step 5: Update Planning State
- Update only the selected ticket line in `docs/planning/ticket-tracker.md`.
- Use:
  - `[x]` if the verification gate is satisfied
  - `[-]` if meaningful partial implementation exists but the ticket is not complete
- Keep the tracker summary counts in sync if you change a ticket status.
- Do not change unrelated ticket statuses.

## 5. Verification Guidance

Use the repo's actual Python and Django tooling, not assumptions from another project.

Prefer commands like:
- focused Django tests for the affected area
- `python -m unittest ...` for current test modules when appropriate
- `python manage.py test ...` for Django app tests

When relevant:
- verify migrations apply cleanly
- verify admin behavior for admin tickets
- verify permissions and ownership boundaries for user-facing tickets
- verify notification records and console delivery behavior for MVP email tickets
- verify no real external provider or gateway was introduced where the docs say the flow is fake or deferred

## 6. Definition Of Done

A ticket is done only if all of the following are true:
- deliverables are implemented
- acceptance criteria are satisfied
- non-goals were respected
- verification gate was actually checked
- code and tests match the PRD and SDS
- tracker status was updated honestly

## 7. Failure Conditions

Stop and report instead of guessing if:
- the ticket conflicts with the PRD, SDS, or track definition
- a dependency ticket is missing and blocks honest completion
- finishing the ticket would require making a major architecture decision not already locked in the planning docs
- the only way to complete the ticket is to violate its `Non-goals`

## 8. Ticket Context: {Ticket}

Insert the full ticket definition here before executing:
- ticket title and ID
- phase
- depends on
- blocks
- deliverables
- acceptance criteria
- non-goals
- verification gate

Implement the ticket now, but do not exceed the ticket boundary.
