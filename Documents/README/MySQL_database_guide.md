# HomeFinder DB Runbook (Step 8)

This guide explains how to run and operate the MySQL database for this project.

## 1. Prerequisites

1. Open Docker Desktop and make sure it is running.
2. Open a terminal in project root
3. Make sure `docker-compose.yml` exists in root.

## 2. Start The Database

```bash
docker compose up -d db
```

What it does:
1. Starts only the `db` service.
2. Runs in background (`-d`).
3. Uses persistent storage volume so data survives restarts.

## 3. Check Status And Logs

Check if DB is healthy:

```bash
docker compose ps
```

View recent logs:

```bash
docker compose logs --tail=100 db
```

Follow logs live:

```bash
docker compose logs -f db
```

Stop following logs: `Ctrl + C`

## 4. Connect To MySQL

Connect as root (interactive):

```bash
docker compose exec db mysql -uroot -p
```

Connect as app user (interactive):

```bash
docker compose exec db mysql -uhomefinder_app -p homefinder
```

Inside MySQL you can try running these commands:

```sql
SHOW DATABASES;
USE homefinder;
SHOW TABLES;
```

Exit MySQL:

```sql
exit;
```

## 5. Run Seed Data

(Seed data is the dummy data that we have made to demonstrate functionality)

Recommended command (works with file redirection):

```bash
docker compose exec -e MYSQL_PWD='admin' -T db mysql -uroot homefinder < internal/db/seed_v1.sql
```

Note:
1. Replace `'admin'` if your root password is different.
2. `-T` is required because input is redirected from file.

## 6. Quick Verification

```bash
docker compose exec db mysql -uroot -padmin -e "USE homefinder; SELECT role, COUNT(*) AS cnt FROM users GROUP BY role; SELECT COUNT(*) AS properties_count FROM properties; SELECT COUNT(*) AS favorites_count FROM user_favorites; SELECT COUNT(*) AS inquiries_count FROM property_inquiries; SELECT COUNT(*) AS bookings_count FROM booking_requests;"
```

Expected:
1. Users: 1 `ADMIN`, 1 `SUPERVISOR`, 2 `USER`
2. Properties: 3
3. Favorites/Inquiries/Bookings: non-zero

## 7. Stop / Restart / Reset

Stop DB container only:

```bash
docker compose stop db
```

Stop and remove containers/network (keep DB data):

```bash
docker compose down
```

Start again:

```bash
docker compose up -d db
```

Reset everything (destructive: deletes DB data):

```bash
docker compose down -v
docker compose up -d db
```

## 8. Common Errors And Fixes

`Cannot connect to the Docker daemon`
1. Docker Desktop is not running.
2. Open Docker Desktop, wait until ready, re-run command.

`Access denied for user 'root'@'localhost'`
1. Wrong password.
2. Verify with:
   `docker compose exec db mysql -uroot -p -e "SELECT 1;"`
3. If credentials are broken and data is disposable, reset with:
   `docker compose down -v && docker compose up -d db`

`Bind for 0.0.0.0:<port> failed: port is already allocated`
1. Another process/container is using that port.
2. Change port mapping in `docker-compose.yml`, then restart.

Tables missing after schema changes
1. Init SQL runs only on first creation of an empty DB volume.
2. For a clean reinit, run:
   `docker compose down -v && docker compose up -d db`
