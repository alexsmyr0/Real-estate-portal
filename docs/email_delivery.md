# Email Delivery Configuration

HomeFinder sends notifications through Django's `EMAIL_BACKEND` setting. The
`EmailNotificationService` persists `EmailNotification` records before delivery,
so switching backends does not change notification persistence or status
handling.

## Console Backend

Use the console backend for local development, tests, and demos. It prints email
content to stdout and requires no provider credentials.

```env
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=HomeFinder <no-reply@homefinder.local>
```

This is the default when no email environment variables are provided.

## SMTP Provider Backend

Use Django's SMTP backend for production-like email delivery. Credentials should
come from environment variables, not source control.

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DEFAULT_FROM_EMAIL=HomeFinder <no-reply@example.com>
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=replace-with-provider-username
EMAIL_HOST_PASSWORD=replace-with-provider-password
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
EMAIL_TIMEOUT=10
```

Most providers document the host, port, username, password, and TLS/SSL values
for SMTP. After changing these variables, restart the Django process so the new
settings are loaded.
