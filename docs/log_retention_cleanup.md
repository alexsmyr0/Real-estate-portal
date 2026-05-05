# Log Retention Cleanup

HomeFinder keeps log-style records for 90 days. The cleanup job is intentionally scoped to these tables only:

- `activity_logs` through `ActivityLog`
- `search_history` through `SearchHistory`
- `email_notifications` through `EmailNotification`

The job deletes rows whose `created_at` is strictly older than the cutoff: `now() - 90 days`. Rows created exactly at the cutoff, or newer than the cutoff, are preserved.

## Never Deleted By This Job

The retention job must not delete primary business records or accounts, including:

- `properties`
- `user_favorites`
- `property_inquiries`
- `viewing_requests`
- `booking_requests`
- `users`

## Manual Execution

Preview eligible rows without deleting anything:

```bash
python manage.py cleanup_log_retention --dry-run
```

Run the cleanup:

```bash
python manage.py cleanup_log_retention
```

The command prints the cutoff timestamp and per-model counts for `ActivityLog`, `SearchHistory`, and `EmailNotification`.

## Scheduling

The command can be scheduled from cron or any deployment scheduler. A daily off-hours cron entry for a virtualenv-based deployment can use:

```cron
0 2 * * * cd /srv/homefinder && /srv/homefinder/.venv/bin/python manage.py cleanup_log_retention >> /var/log/homefinder-retention.log 2>&1
```

For the Docker Compose deployment shape, schedule the command from the host with:

```cron
0 2 * * * cd /srv/homefinder && docker compose exec -T app python manage.py cleanup_log_retention >> /var/log/homefinder-retention.log 2>&1
```
