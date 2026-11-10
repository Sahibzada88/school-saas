# Deployment: frontend and backend on Vercel (+ Supabase database)

Architecture: **two Vercel projects** from one GitHub repo and **one Supabase PostgreSQL** database.

```
Browser --> Vercel project "web" (Next.js, frontend/)  --proxy.ts rewrites /api/v1/*-->  Vercel project "api" (Django, backend/)  --> Supabase
```

The browser only ever talks to the **web** project, so cookies are first-party. `proxy.ts` forwards the real client IP together with `PROXY_SHARED_SECRET`, so the backend can trust it.

> Hobby plans are for non-commercial use. Before charging real schools, move both projects to a Vercel Pro plan.

How the backend is deployed (current Vercel behaviour, checked against the Vercel Django docs): Vercel detects `backend/manage.py`, reads `WSGI_APPLICATION` (`config.wsgi.application`) and turns the whole Django app into one Vercel Function. There is **no `api/` folder and no `vercel.json` rewrite** any more. `config/wsgi.py` forces `config.settings.production` whenever Vercel runs it. Fallback if detection ever fails: `docs/vercel-legacy-backend/README.md`.

---

## Step 1: Put the code on GitHub

```powershell
cd "D:\My personal projects\school-saas"
git init
git add .
git status          # check: no .env, no node_modules, no .venv in the list
git commit -m "School SaaS"
git branch -M main
git remote add origin https://github.com/<your-user>/school-saas.git
git push -u origin main
```

Before pushing, commit the generated migrations too (`git add backend/apps/*/migrations`). `git status` must not show any `.env*` files except `.env.example` files.

## Step 2: Supabase (database)

1. Create a project at supabase.com. Pick the region nearest your users (for Pakistan: Mumbai `ap-south-1`) and remember it.
2. Open **Connect** (or Project Settings -> Database) and copy two connection strings:
   - **Transaction pooler**, port **6543**: this is `DATABASE_URL` (used by the running app).
   - **Session pooler**, port **5432**: this is `DIRECT_URL` (used by migrations and backups).
3. Replace `[YOUR-PASSWORD]` in both strings with your database password. URL-encode special characters (`@` -> `%40`, `#` -> `%23`, `/` -> `%2F`). Keep `?sslmode=require` at the end.

## Step 3: Decide names and generate secrets

Choose the two Vercel project names now, so the URLs are known in advance:

| Project | Name (example) | Production URL |
|---|---|---|
| Backend | `school-saas-api` | `https://school-saas-api.vercel.app` |
| Frontend | `school-saas-web` | `https://school-saas-web.vercel.app` |

If a name is already taken, Vercel adds a suffix. After creating each project, check **Settings -> Domains** for the real production URL and use that everywhere below.

Generate three secrets (PowerShell, any Python 3 on your PC):

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"   # SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(64))"   # JWT_SIGNING_KEY
python -c "import secrets; print(secrets.token_urlsafe(48))"   # PROXY_SHARED_SECRET (32+ chars, same value on BOTH projects)
```

## Step 4: Create the backend project (Django)

1. Vercel dashboard -> **Add New -> Project** -> import your GitHub repo.
2. **Project Name**: `school-saas-api`. **Root Directory**: click *Edit* and choose `backend`.
3. **Framework Preset** should show **Django**. If it shows *Other*, change it to Django. Leave Build/Install/Output commands at their defaults (do **not** add `collectstatic` or `migrate`).
4. Open **Environment Variables** (on this same screen, before deploying) and add, for *Production* (and *Preview* if you will use previews):

| Name | Value |
|---|---|
| `SECRET_KEY` | the first secret |
| `JWT_SIGNING_KEY` | the second secret |
| `DATABASE_URL` | transaction pooler string (port **6543**) |
| `FRONTEND_ORIGIN` | `https://school-saas-web.vercel.app` (no trailing slash) |
| `PROXY_SHARED_SECRET` | the third secret |
| `ENVIRONMENT` | `production` |
| `DEBUG` | `False` |
| `DJANGO_SETTINGS_MODULE` | `config.settings.production` |
| `EMAIL_BACKEND` | `smtp` plus `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_FROM` (optional; without it emails are skipped and logged) |
| `ALLOWED_HOSTS` | only needed for a **custom** domain, e.g. `api.yourschool.com` (the `*.vercel.app` hostnames are added automatically) |

   Do **not** set `DJANGO_USE_DIRECT_URL` on Vercel (it would make the running app use the 5432 string).
   The variables must exist **before the first deploy**: the build runs `manage.py`, which imports the settings and needs `DATABASE_URL`.
5. Click **Deploy**.
6. After it finishes: **Settings -> Functions -> Function Region**: choose the region closest to Supabase (Mumbai `bom1` for `ap-south-1`) and redeploy once. Keeping the function and the database in the same region makes every request noticeably faster.
7. Test: open `https://school-saas-api.vercel.app/api/v1/health/?db=1`. Expected: `{"success": true, ...}` with `"database": "ok"`. (The root URL `/` returns 404 on purpose: this is an API.)

   If you see a **Vercel login page** or `401` instead: Settings -> Deployment Protection. Use the production domain, not a per-deployment hash URL, and make sure the production domain is not protected.

## Step 5: Create the tables in the production database (once, from your PC)

Migrations never run on Vercel. Run them from your PC against the Supabase **session pooler**:

```powershell
cd "D:\My personal projects\school-saas"
Copy-Item backend\.env.production.example backend\.env.production
notepad backend\.env.production          # fill DIRECT_URL, DATABASE_URL, SECRET_KEY, FRONTEND_ORIGIN, PROXY_SHARED_SECRET, ALLOWED_HOSTS
cd backend; .venv\Scripts\Activate.ps1; cd ..

.\scripts\prod-manage.ps1 migrate                      # asks you to type YES, then creates all tables
.\scripts\prod-manage.ps1 bootstrap_school_defaults    # harmless on an empty database
.\scripts\prod-manage.ps1 check_rls                    # must print: All public tables have RLS enabled.
.\scripts\prod-manage.ps1 createsuperuser              # the platform owner account (Argon2 password hash)
```

`backend/.env.production` is git-ignored: never commit it. If `migrate` says there are model changes without migrations, run `python manage.py makemigrations` locally, commit the new files, push, then migrate again.

## Step 6: Create the frontend project (Next.js)

1. **Add New -> Project** -> the same repo.
2. **Project Name**: `school-saas-web`. **Root Directory**: `frontend`. **Framework Preset**: Next.js (automatic).
3. **Environment Variables**:

| Name | Value |
|---|---|
| `BACKEND_ORIGIN` | `https://school-saas-api.vercel.app` (the backend production URL, no trailing slash) |
| `PROXY_SHARED_SECRET` | the **same** third secret |
| `NEXT_PUBLIC_API_URL` | `/api/v1` |

4. **Deploy**. Then **Settings -> Functions -> Function Region** = the same region as the backend, and redeploy.
5. Make sure the frontend's real production URL equals the `FRONTEND_ORIGIN` you gave the backend. If it differs, fix `FRONTEND_ORIGIN` on the backend project and redeploy the backend.
6. `frontend/vercel.json` adds a daily cron that calls the health endpoint with a database query. It also keeps the free Supabase project from pausing after a week of inactivity.

## Step 7: Check everything works

1. `https://school-saas-web.vercel.app/api/v1/health/?db=1`: same JSON as in Step 4, but through the frontend proxy. If this works, the two projects are connected correctly.
2. `https://school-saas-web.vercel.app`: redirects to `/login`, page is styled.
3. Log in with the superuser from Step 5: you land on `/platform/dashboard`.
4. In a private window: **Register** a school. You land on its dashboard.
5. DevTools -> Application -> Cookies: `access_token` and `refresh_token` are **HttpOnly** and **Secure**.
6. Platform -> Audit logs: the registration event shows a **real IP address**. If it shows a Vercel-internal address, the two `PROXY_SHARED_SECRET` values differ.
7. Run the rest of the manual script in `README.md` (sections 1 to 13) against the production URL.

## Step 8: Custom domain (optional)

1. Frontend project -> Settings -> Domains -> add `app.yourschool.com`, follow the DNS instructions.
2. Update `FRONTEND_ORIGIN` on the **backend** project to `https://app.yourschool.com`, redeploy the backend.
3. Backend: keep `BACKEND_ORIGIN` pointing at its `*.vercel.app` URL (no custom domain needed for the API). If you do give the API its own domain, add that host to `ALLOWED_HOSTS` on the backend.

## Updating later

- `git push` to `main` redeploys both projects automatically (only the one whose folder changed).
- Changing models: `makemigrations` locally -> commit -> **run `.\scripts\prod-manage.ps1 migrate` first** -> then push. Take a backup before destructive migrations.
- Changing an env var: edit it in Vercel, then **Redeploy** (env changes apply to new deployments only).
- Rollback: Vercel -> Deployments -> pick an older deployment -> *Promote to Production*. Database changes are forward-only.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Backend build fails: `DATABASE_URL is not set` | Add the env vars (Step 4) and redeploy. The build imports the settings. |
| Backend build fails: `ImproperlyConfigured ... SECRET_KEY / FRONTEND_ORIGIN / PROXY_SHARED_SECRET` | Fix that variable: SECRET_KEY >= 50 chars, FRONTEND_ORIGIN starts with `https://`, PROXY_SHARED_SECRET >= 32 chars. |
| Every backend URL gives `404: NOT_FOUND` (Vercel page) | Django was not detected. Check Root Directory = `backend`, Framework Preset = Django; else use Plan B (`docs/vercel-legacy-backend/README.md`). |
| `DisallowedHost` in function logs | Custom domain missing: add it to `ALLOWED_HOSTS`. |
| `/api/v1/health/` is OK on the backend but 500/502 on the frontend | `BACKEND_ORIGIN` wrong (use the production URL, `https://`, no trailing slash) or Deployment Protection is on for the backend. |
| `403` on every POST/PATCH/DELETE | `FRONTEND_ORIGIN` on the backend must equal the frontend's real URL exactly. Also call the API only through the frontend URL. |
| Login works, then you are logged out on the next page | Cookies blocked: you are using the backend URL directly, or `PROXY_SHARED_SECRET` differs. Use the frontend URL only. |
| `database: "error"` in health | Wrong `DATABASE_URL` (password encoding, port 6543, `?sslmode=require`) or Supabase project paused: open the Supabase dashboard and restore it. |
| `prepared statement ... does not exist` | `DATABASE_URL` must be the **6543 transaction pooler** string; the app already disables prepared statements for it. |
| Very slow first request after idle | Cold start (Django imports). Normal on the free plan; same-region function + database keeps it to a couple of seconds. |
| Upload or download fails with 413 | Vercel limits request/response bodies to about 4.5 MB. CSV imports are capped at 1 MB, images at 150-300 KB; narrow big exports (the app already caps rows). |

## Operations

- **Backups:** free Supabase has none. Run `.\scripts\backup.ps1 -Url "<DIRECT_URL>"` regularly (needs `pg_dump`) and keep the files safe. Restore command is in the script header.
- **Database size:** free tier = 500 MB. Photos and logos live in the database (photos 150 KB, logos 300 KB, 50 MB per school, configurable under Platform -> Settings).
- **Secrets rotation:** changing `SECRET_KEY` / `JWT_SIGNING_KEY` signs everyone out. Changing `PROXY_SHARED_SECRET` means updating **both** projects and redeploying both.
- **No background workers:** trial/subscription expiry, notices and emails are derived or created lazily during requests.

## Production security checklist

- [ ] `DEBUG=False`; SECRET_KEY, JWT_SIGNING_KEY, PROXY_SHARED_SECRET are random and private.
- [ ] `check_rls` passed against the production database.
- [ ] No Supabase `anon` / `service_role` key is used or exposed anywhere.
- [ ] Cookies are `HttpOnly` + `Secure`; CSRF header required on every write.
- [ ] `FRONTEND_ORIGIN` / `ALLOWED_HOSTS` list only your own domains.
- [ ] The Super Admin uses a strong, unique password.
- [ ] SMTP configured (password resets depend on it) with SPF/DKIM on your sending domain.
- [ ] Backups scheduled and one restore tested.
- [ ] Vercel plan matches your usage terms (commercial use).
- [ ] `python manage.py test` passes (isolation matrix, route guards) before every release.
