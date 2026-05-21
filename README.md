# HomeFinder

HomeFinder is an online real estate portal: users browse, search, favorite, and inquire about residential, commercial, and rental properties. The implementation is a server-rendered Django monolith on MySQL, with custom staff pages alongside Django admin. The canonical scope reference is the submission SDS; [docs/planning/sds.md](docs/planning/sds.md) is the older internal planning doc and may lag the code.

## Stack

- **Backend:** Django 5.x (Python 3.12+)
- **Database:** MySQL 8.4 (SQLite in-memory for tests)
- **Frontend:** Django templates + light progressive-enhancement JS (no SPA, no separate frontend app)
- **Auth:** custom user model (email login) + email 2FA + single active session
- **Email:** Django console backend by default (real SMTP is post-MVP)
- **Container:** Docker Compose for app + MySQL

## Repository Layout

```
.
├── manage.py                 # Django entrypoint (adds src/ to sys.path)
├── pyproject.toml            # Package metadata (package-dir = src)
├── requirements.txt          # Django, PyMySQL, cryptography
├── docker-compose.yml        # app + MySQL services
├── Dockerfile                # Python 3.12-slim image
├── .env.example              # Copy to .env for local overrides
├── src/homefinder/
│   ├── settings.py           # Reads config via homefinder.config.load_settings
│   ├── test_settings.py      # In-memory SQLite + fast hasher
│   ├── urls.py               # Root URLConf (admin + 4 app includes)
│   └── apps/
│       ├── core/             # Home page, health endpoint, error handlers
│       ├── users/            # Custom User, 2FA tokens, ActiveSession, auth views
│       ├── properties/       # Property/Amenity/Image, catalog, favorites, staff CRUD, reporting
│       └── interactions/     # Inquiries, viewings, bookings, dashboard, staff queues
├── templates/                # Project-level templates (base.html + per-app folders)
├── tests/                    # Django TestCase suites grouped by flow
└── docs/                     # Planning docs (sds.md, prd.md, scenario, DB guide)
```

## First-Time Setup

### 1. Clone and create a virtualenv

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install --no-deps -e .
```

### 2. Copy the env file

```bash
cp .env.example .env
```

Defaults work for local dev. Override `MYSQL_*` and `DB_*` if you want different credentials. `APP_DEBUG=true` and the console email backend are already set.

### 3. Start MySQL

Easiest path is the bundled Docker Compose:

```bash
docker compose up -d db
```

This brings up MySQL 8.4 on `127.0.0.1:3306` with database `homefinder` and user `homefinder_app / admin`. Data persists in the `mysql_data` volume.

If you have a local MySQL already, point `.env` at it instead — any MySQL 8.x works.

### 4. Apply migrations

```bash
python manage.py migrate
```

### 5. Run the dev server

```bash
python manage.py runserver 0.0.0.0:8080
```

App is at http://127.0.0.1:8080/ and admin is at http://127.0.0.1:8080/admin/.

## Full Stack via Docker (alternative)

```bash
docker compose up -d
```

This builds the app image, starts MySQL, waits for it to be healthy, runs migrations, and serves on port 8080. Use this if you'd rather not install Python locally.

## Seeding Data

A repeatable demo catalog (properties, amenities, images) ships as a Django management command:

```bash
python manage.py seed_demo_catalog
```

Re-running it is safe — the command is idempotent.

There is also a legacy `src/homefinder/db/seed_v1.sql`; **do not load it** against the Django-managed schema. Use the management command instead.

## Creating Accounts

### Standard user

Register via the UI at `/register/`, or in a shell:

```bash
python manage.py shell -c "from homefinder.apps.users.models import User; User.objects.create_user(email='user@example.com', password='changeme123')"
```

### Django superuser (full admin)

```bash
python manage.py createsuperuser
```

This creates a user with `is_staff=True`, `is_superuser=True`, and `role=ADMIN` — full access to Django admin and the staff areas.

### Promoting an existing account to admin or supervisor

There are three roles defined in [src/homefinder/apps/users/models.py](src/homefinder/apps/users/models.py): `USER`, `SUPERVISOR`, `ADMIN`. Promote from the shell:

```bash
# Promote to ADMIN (full admin + Django admin access)
python manage.py shell -c "
from homefinder.apps.users.models import User, UserRole
u = User.objects.get(email='someone@example.com')
u.role = UserRole.ADMIN
u.is_staff = True
u.is_superuser = True
u.save()
"

# Promote to SUPERVISOR (read-only reporting access, no Django admin)
python manage.py shell -c "
from homefinder.apps.users.models import User, UserRole
u = User.objects.get(email='someone@example.com')
u.role = UserRole.SUPERVISOR
u.save()
"
```

`is_staff` controls access to Django admin (`/admin/`). `role` controls access to the in-app staff and reporting pages.

## Running Tests

The test runner uses an in-memory SQLite database and a fast password hasher — no MySQL required.

```bash
# Full suite
python manage.py test

# A single module
python manage.py test tests.test_auth_flows

# A single test
python manage.py test tests.test_auth_flows.AuthFlowTests.test_login_requires_2fa
```

## Useful URLs

| Path | Purpose |
| --- | --- |
| `/` | Site home |
| `/register/`, `/login/`, `/login/2fa/`, `/logout/` | Auth flows |
| `/catalog/` | Property listings with filters (12/page) |
| `/catalog/<id>/` | Property detail |
| `/saved-listings/` | User favorites |
| `/dashboard/` | Authenticated user dashboard |
| `/staff/listings/` | Staff listing CRUD |
| `/staff/interactions/inquiries/`, `/viewings/`, `/bookings/` | Staff interaction queues |
| `/staff/reports/` | Supervisor reporting (read-only, SUPERVISOR/ADMIN only) |
| `/admin/` | Django admin |
| `/api/v1/health/` | Health probe |

## Environment Variables

See [.env.example](.env.example) for the full list. The most relevant ones:

| Variable | Default | Notes |
| --- | --- | --- |
| `APP_PORT` | `8080` | Dev server port |
| `APP_DEBUG` | `true` | Set `false` for prod-like runs |
| `APP_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated |
| `DB_HOST` | `127.0.0.1` | `db` inside Compose |
| `DB_SCHEME` | `mysql` | Also accepts `postgres` or `sqlite` |
| `MYSQL_DATABASE` / `MYSQL_USER` / `MYSQL_PASSWORD` | `homefinder` / `homefinder_app` / `admin` | |
| `EMAIL_BACKEND` | `django.core.mail.backends.console.EmailBackend` | 2FA codes print to the runserver console |
| `DJANGO_SECRET_KEY` | dev placeholder | **Override in any non-dev environment** |

## Common Operations

| Task | Command |
| --- | --- |
| Apply new migrations | `python manage.py migrate` |
| Make migrations after model changes | `python manage.py makemigrations` |
| Open Django shell | `python manage.py shell` |
| Open MySQL shell (Compose) | `docker compose exec db mysql -uhomefinder_app -p homefinder` |
| Tail DB logs | `docker compose logs -f db` |
| Reset DB (destroys data) | `docker compose down -v && docker compose up -d db && python manage.py migrate` |
| Seed demo catalog | `python manage.py seed_demo_catalog` |

## Where to Read Next

- [docs/planning/sds.md](docs/planning/sds.md) — Software design spec (architecture, flows, locked decisions)
- [docs/planning/prd.md](docs/planning/prd.md) — Product requirements
- [docs/project_scenario.md](docs/project_scenario.md) — Original assignment scenario
- [docs/MySQL_database_guide.md](docs/MySQL_database_guide.md) — DB operations runbook
- [docs/email_delivery.md](docs/email_delivery.md) — Email backend notes
- [docs/log_retention_cleanup.md](docs/log_retention_cleanup.md) — Retention rules for logs/search history

## MVP vs. Post-MVP

The MVP now ships the full HomeFinder flow: registration, login with email 2FA, single-active-session enforcement, GDPR consent, browsing the three property categories (residential, commercial, rental), favorites, inquiries, viewing requests, booking requests with simulated payments (credit card, bank transfer, booking fee), similar-listing alert subscriptions, the user dashboard with personalized recommendations, custom staff pages, supervisor reporting (read-only), and 3-month log retention via the `cleanup_log_retention` management command.

Still post-MVP: real SMTP email delivery (console backend is the default), a real payment gateway (payments are simulated), advanced analytics and performance benchmarking, and the mobile app referenced in the project scenario.
