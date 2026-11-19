# Free uptime and error monitoring

SasthoSetu already exposes two safe monitoring endpoints:

- `GET /health` confirms that the process is alive.
- `GET /ready` verifies the database schema and required triage/surge model
  artifacts. It returns HTTP 503 if the deployment should not receive traffic.

## UptimeRobot (free)

1. Create an HTTPS monitor for `https://sasthosetu.onrender.com/health`.
2. Create a second HTTPS monitor for `https://sasthosetu.onrender.com/ready`.
3. Set the expected status to 200 and add the project operator's email alert.
4. Do not put authenticated URLs, patient identifiers, query strings or API
   tokens into a third-party monitor.

The free monitoring plan and its limits are controlled by the provider, so
confirm them in its dashboard before relying on an alert.

## Sentry (optional)

Create a Sentry Python/FastAPI project, then set `SENTRY_DSN` in Render. The
application initializes it only when that setting is present and configures
`send_default_pii=False`. Start with `SENTRY_TRACES_SAMPLE_RATE=0.0`; increase
it only after reviewing data governance and cost implications.

## Aggregate alert webhook (optional)

The admin Operations tab previews threshold breaches. To enable delivery, put
an HTTPS Discord/Slack/Teams-compatible webhook URL in `ALERT_WEBHOOK_URL` and
set `ALERT_WEBHOOK_ENABLED=true`. The payload contains only aggregate error and
latency alerts plus release metadata; it never contains symptom text, images,
patient identifiers, access tokens or credentials. An administrator can invoke
`POST /api/v1/admin/operations/dispatch-alerts` to verify the configuration.
