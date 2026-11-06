# Deployment runbook (Vercel + Supabase)

Architecture: **two Vercel projects** (Next.js frontend, Django backend) and **one Supabase PostgreSQL** database.
The browser only talks to the frontend; `proxy.ts` forwards `/api/v1/*` to the backend, so cookies are first-party.

> Hobby plans are for non-commercial use. Before charging real schools, upgrade the Vercel plan (or move only the Django project to another host: it is a plain WSGI app).

## 0. Before you start

- Code is in a GitHub repository (monorepo: `backend/`, `frontend/`).
- Locally verified: `python manage.py test` passes and `npm run lint && npx tsc --noEmit` pass.
- Migrations are committed (`python manage.py makemigrations --check --dry-run` reports nothing).

## 1. Supabase

1. Create a project; choose the region nearest your users and note it (the Vercel function region must match).
2. **Project Settings → Database → Connection string**: copy
   - **Transaction pooler** (port 6543) → this is the runtime `DATABASE_URL`;
   - **Session pooler** (port 5432) → `DIRECT_URL`, for migrations and backups.
3. URL-encode special characters of the password.
4. From your machine (PowerShell, in `backend` with the venv active), with `DIRECT_URL` in `.env`:

```powershell
$env:DJANGO_USE_DIRECT_URL = "1"
python manage.py migrate
python manage.py bootstrap_school_defaults      # no-op on an empty database
python manage.py check_rls                       # must print: All public tables have RLS enabled.
python manage.py createsuperuser                 # the platform owner account
Remove-Item Env:DJANGO_USE_DIRECT_URL
```

5. Optionally create your first plans in the app (Platform → Plans). `seed_plans` is development data only.

## 2. Backend project (Vercel)

1. **Add New → Project**, import the repo, **Root Directory = `backend`**, Framework preset **Other**.
2. Environment variables (Production):

| Variable | Value |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.production` |
| `ENVIRONMENT` | `production` |
| `SECRET_KEY` | 50+ random characters |
| `JWT_SIGNING_KEY` | another random value (recommended) |
| `DATABASE_URL` | transaction pooler string (6543) |
| `ALLOWED_HOSTS` | the backend hostname, e.g. `school-saas-api.vercel.app` |
| `FRONTEND_ORIGIN` | `https://<your-frontend-domain>` |
| `CSRF_TRUSTED_ORIGINS` | same as `FRONTEND_ORIGIN` |
| `CORS_ALLOWED_ORIGINS` | same as `FRONTEND_ORIGIN` |
| `PROXY_SHARED_SECRET` | 32+ random characters, **identical on the frontend project** |
| `EMAIL_BACKEND` | `smtp` (plus `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_FROM`) or leave unset: email is then skipped and logged |

Generate secrets: `python -c "import secrets; print(secrets.token_urlsafe(64))"`.

3. Project Settings → Functions → set the **region** to the Supabase region.
4. Deploy, then check `https://<backend>/api/v1/health/?db=1` returns `{"success": true, ...}` with `"database": "ok"`.

## 3. Frontend project (Vercel)

1. **Add New → Project**, same repo, **Root Directory = `frontend`**, framework Next.js.
2. Environment variables:

| Variable | Value |
|---|---|
| `BACKEND_ORIGIN` | `https://<backend>.vercel.app` (no trailing slash) |
| `NEXT_PUBLIC_API_URL` | `/api/v1` |
| `PROXY_SHARED_SECRET` | the same value as the backend |

3. Deploy. `frontend/vercel.json` adds a daily cron that calls the health endpoint (with a database query), which also stops the free Supabase project from pausing after a week of inactivity. Nothing depends on it.
4. Custom domain (optional): attach it to the frontend project; update `FRONTEND_ORIGIN`, `CSRF_TRUSTED_ORIGINS` and `CORS_ALLOWED_ORIGINS` on the backend and redeploy it.

## 4. Smoke test (production)

1. Open the frontend URL: it must redirect to `/login`.
2. Register a school: you land on the dashboard; the welcome email arrives (if SMTP is configured).
3. In the browser dev tools (Application → Cookies) `access_token` and `refresh_token` must be **HttpOnly** and **Secure**.
4. Sign in as the Super Admin; open Platform → Schools; the new school is listed with a trial.
5. Add a class, a section, a student; enrol the student; mark attendance; download the student list PDF.
6. Platform → school → Subscription → Record payment; the school admin sees the notification.
7. Platform → Audit logs shows the registration, payment and export events.
8. Check client IPs in the audit log are real addresses (not Vercel internals). If they are not, the two `PROXY_SHARED_SECRET` values differ.

## 5. Operations

- **Backups:** the free tier has none. Run `.\scripts\backup.ps1 -Url "<DIRECT_URL>"` regularly (needs `pg_dump`) and keep the files somewhere safe. Restore command is in the script header.
- **Database size:** free tier = 500 MB. Student/teacher photos and logos live in the database (limits: photos 150 KB, logos 300 KB, 50 MB per school, configurable under Platform → Settings). Watch the Supabase dashboard.
- **Migrations:** run them from your machine with `DJANGO_USE_DIRECT_URL=1`, *before* deploying code that needs them. Never run migrations during a Vercel build.
- **Rollback:** Vercel → Deployments → promote the previous deployment. Database changes are forward-only: take a backup before destructive migrations.
- **Secrets rotation:** changing `SECRET_KEY`/`JWT_SIGNING_KEY` signs every user out (acceptable). Changing `PROXY_SHARED_SECRET` requires redeploying both projects together.

## 6. Serverless limits to keep in mind

- Function time and memory limits depend on your Vercel plan: check the current limits for your plan.
- CSV exports are capped at 20,000 rows and PDFs at 500 rows per request (HTTP 413 with a hint to narrow filters). Invoice generation is capped at 1,000 students per run (generate per section).
- No background workers exist: trial/subscription expiry, notifications and emails are derived or created lazily on requests.
- For much larger exports later: generate in a scheduled job or worker and store the file in object storage (not built, by design).

## 7. Production security checklist

- [ ] `DEBUG` is off; `SECRET_KEY`, `JWT_SIGNING_KEY`, `PROXY_SHARED_SECRET` are random and private.
- [ ] `check_rls` passes (no table is reachable through Supabase's public API).
- [ ] No Supabase `anon` / `service_role` key is used or exposed anywhere.
- [ ] Cookies are `HttpOnly`, `Secure`, `SameSite=Lax`; CSRF header required on every write (verified by tests).
- [ ] `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS` list only your domains.
- [ ] Super Admin account uses a strong, unique password; only platform staff have it.
- [ ] Email provider configured (password resets depend on it) and SPF/DKIM set for your sending domain.
- [ ] Backups scheduled and a restore has been tested once.
- [ ] Vercel plan matches your usage terms (commercial use).
- [ ] Tenant isolation matrix and route guards pass in CI (`python manage.py test`).
