# School SaaS

Multi-tenant School Management SaaS.

**Stack:** Next.js (App Router, TypeScript, Tailwind, shadcn/ui) · Django REST Framework · Supabase PostgreSQL · Vercel (two projects).
No Redis, no Celery, no background workers, no object storage. PDFs and CSVs are generated in memory per request.

> Status: **All phases built (1-14)**: foundation, auth + tenancy, school lifecycle, SaaS billing, students & guardians, teachers & academics, attendance, examinations & results, fees, reports (PDF/CSV), announcements & email, UI, security guards, deployment runbook. Code abhi tak kisi real database par run nahi hua: pehli `makemigrations`/`migrate`/`test` runs mein errors aa sakte hain, wahi next debugging round hai. Going live: `docs/DEPLOYMENT.md`.

## Architecture

```
Browser ──► Vercel A: Next.js ── middleware proxies /api/v1/* ──► Vercel B: Django (WSGI serverless) ──► Supabase Postgres (pooler)
```

The browser only talks to the Next.js origin. The Next.js proxy (proxy.ts) proxies `/api/v1/*` to Django (and forwards the real client IP, signed with a shared secret), so auth cookies are first-party.

## Repository layout

```
backend/    Django project (config/, apps/, api/index.py = Vercel entrypoint)
frontend/   Next.js app (sirf project ki apni files; baqi "Frontend setup" ke commands se banti hain)
docker-compose.yml   optional local dev (Postgres + backend + frontend, Docker Desktop)
```

---

## Local development (Windows)

Sab commands **Windows PowerShell** ke liye hain. Zaroori cheezein: Python 3.12, Node.js 20+, Git, aur (database ke liye) Docker Desktop.
VS Code mein 2 terminals kholein: ek backend ke liye, ek frontend ke liye.

### 0. Database (local Postgres, Docker Desktop)

Docker Desktop chalu karein (WSL 2 backend), phir repository ki root folder (`school-saas`) mein:

```powershell
docker compose up db -d
docker compose ps          # db "healthy" dikhna chahiye
```

### 1. Backend

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

Agar activate par "running scripts is disabled" error aaye, ek baar ye chalayein aur dobara activate karein:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Phir:

```powershell
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

`.env` mein kam az kam ye set karein (baqi values local ke liye theek hain):

```
SECRET_KEY=koi-bhi-lambi-random-string-local-ke-liye
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/school_saas
```

Phir tables banayein aur server chalayein:

```powershell
python manage.py makemigrations           # PEHLI BAAR zaroori: naye apps (students, teachers, academics, attendance,
                                          # examinations, fees, ...) ki migrations yahan generate hoti hain; inhein commit karein
python manage.py migrate
python manage.py bootstrap_school_defaults # purane schools ke liye default session/grading/fee categories (naye schools ko khud mil jati hain)
python manage.py check_rls                 # har table par row-level security verify karta hai
python manage.py createsuperuser           # pehla Super Admin: email, first name, last name, password
python manage.py seed_plans                # OPTIONAL: sample Basic/Standard/Pro plans (sirf development data)
python manage.py runserver                 # http://localhost:8000/api/v1/health/?db=1
```

Models badalne ke baad: `python manage.py makemigrations`, phir `python manage.py migrate`.
CI `python manage.py makemigrations --check --dry-run` chalata hai, is liye migrations hamesha commit karein.

### 2. Frontend setup (sirf ek baar)

Repository mein sirf project ki apni frontend files hain. Next.js scaffold, Tailwind aur shadcn files neeche ke commands se banti hain, **bina hamari files overwrite kiye**.

Repository ki root (`school-saas`) se chalayein (naya terminal; `cd ..` agar `backend` mein hain):

```powershell
npx create-next-app@latest frontend-tmp --typescript --tailwind --eslint --app --no-src-dir --import-alias "@/*" --use-npm --skip-install
robocopy frontend-tmp frontend /E /XC /XN /XO
Remove-Item -Recurse -Force frontend-tmp
```

`robocopy` sirf wo files copy karta hai jo `frontend` mein pehle se nahi hain. Uske exit codes 0 se 7 tak **success** hain (error nahi). Agar create-next-app koi sawal pooche to defaults chun lein.

Phir:

```powershell
cd frontend
npm install
npx shadcn@latest init
npm install tw-animate-css class-variance-authority clsx tailwind-merge lucide-react @base-ui/react shadcn
npx shadcn@latest add button
npm install @tanstack/react-query react-hook-form zod @hookform/resolvers recharts lucide-react next-themes
copy .env.example .env.local
```

`shadcn init` mein defaults accept karein (Base UI + Nova theek hain). Check karein ke ye 4 files scaffold ne **overwrite nahi** kiyeen (inmein hamara code hona chahiye): `app\layout.tsx`, `app\page.tsx`, `next.config.ts`, `proxy.ts`.

**Dhyan:** `npm audit fix --force` kabhi na chalayein. Wo `eslint-config-next` ko purane version par downgrade kar deta hai aur shadcn ka install `ERESOLVE` se fail ho jata hai. Audit ki warnings sirf development tools ki hain.
Agar `npm install` aise hi bigad jaye: `Remove-Item -Recurse -Force node_modules, package-lock.json`, phir `npm install`.

### 3. Frontend chalayein

```powershell
cd frontend
npm run dev                            # http://localhost:3000
```

Browser mein http://localhost:3000 kholein, school register karein, ya apne Super Admin se sign in karein.

### Alternative: sab kuch Docker mein (frontend setup ke baad)

```powershell
docker compose up
```

---

## Supabase setup

1. Project banayein. Region Vercel function region ke sab se qareeb chunein.
2. **Project Settings → Database → Connection string** se copy karein:
   - **Transaction pooler** (port **6543**) → `DATABASE_URL` (runtime, Vercel use karta hai)
   - **Session pooler** (port **5432**, pooler host) → `DIRECT_URL` (migrations)
   - "Direct" `db.<ref>.supabase.co` host free tier par sirf IPv6 hai; session pooler use karein.
3. Password ke special characters URL-encode karein.
4. Migrations apni machine se chalayein, Vercel build mein kabhi nahi (`backend\.env` mein `DIRECT_URL` bhar kar):

```powershell
cd backend
.venv\Scripts\Activate.ps1
$env:DJANGO_USE_DIRECT_URL = "1"
python manage.py migrate
python manage.py check_rls
python manage.py createsuperuser
Remove-Item Env:DJANGO_USE_DIRECT_URL      # normal (pooled) connection par wapas
```

5. Tests ke liye local Postgres use karein (Supabase par nahi), kyun ke Django `test_*` database banata hai.

Har `migrate` ke baad sab public tables par row-level security on ho jati hai aur `anon`/`authenticated` ke grants hat jate hain, yani data tak sirf Django pahunch sakta hai.

## Vercel setup

Ek hi repo se **do** projects banayein.

| Project | Root Directory | Framework | Env vars |
|---|---|---|---|
| backend | `backend` | Other (Python auto-detect) | `backend\.env.example` dekhein; `DJANGO_SETTINGS_MODULE=config.settings.production` |
| frontend | `frontend` | Next.js | `BACKEND_ORIGIN=https://<backend>.vercel.app`, `NEXT_PUBLIC_API_URL=/api/v1`, `PROXY_SHARED_SECRET=<backend wali value>` |

Secrets generate karne ke liye (PowerShell):

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"     # SECRET_KEY (50+ chars)
python -c "import secrets; print(secrets.token_urlsafe(32))"     # PROXY_SHARED_SECRET (dono projects mein ek jaisi)
```

Production checklist: `SECRET_KEY`, `ALLOWED_HOSTS`, `FRONTEND_ORIGIN` (https), `CSRF_TRUSTED_ORIGINS`, `PROXY_SHARED_SECRET` (32+ chars, dono projects mein same), `DATABASE_URL`. Backend function region Supabase ke region ke mutabiq rakhein.

## Modules (Phases 5-11)

- **Students & guardians:** admission with per-school student numbers, profile photo (validated Base64 in PostgreSQL), guardians (link or create inline), status changes, soft delete. Role scope: teacher = own sections, parent = own children, student = self.
- **Teachers & academics:** teachers (linked sign-in account), sessions (one current), classes, sections (capacity), subjects, assignments, enrollments (roll numbers, capacity, move), year-end promotion, timetable (clash protection).
- **Attendance:** daily marking per section (teachers: assigned sections only, 7-day edit window), monthly report and percentage, teacher attendance.
- **Examinations:** exam types, exams (draft -> scheduled -> marks entry -> published -> archived), marks entry (teacher scoped), grading scales, preview, publish (snapshot report cards, grades, positions, pass/fail), transcripts.
- **Fees (student fees, separate from SaaS billing):** categories, structures, idempotent invoice generation, discounts, fines, partial payments, receipts, reversal rules, voiding.
- **Reports:** JSON reports, on-demand PDFs (report card, transcript, receipt, invoice, certificate, attendance, outstanding fees, student list) and CSV exports (formula-injection safe, tenant scoped, audited). Nothing is stored.
- **Announcements & email:** audience-targeted notice board with lazy read receipts; email provider abstraction with logging.

## Testing

```powershell
cd backend
.venv\Scripts\Activate.ps1
python manage.py test                        # local Postgres (Docker) chalu hona zaroori hai
```

```powershell
cd frontend
npm run lint
npx tsc --noEmit
```

---

## What is implemented

### Authentication and tenancy (Phase 2)
- HttpOnly cookies (`access_token` 15 min, `refresh_token` 7 days scoped to `/api/v1/auth/`), refresh rotation with reuse detection, immediate revocation on logout / password change / deactivation.
- CSRF: signed double-submit token (`X-CSRF-Token`) plus `Origin` check on every unsafe `/api/` request, enforced in middleware.
- DB-backed throttling for login, registration and password reset.
- The tenant is always `request.user.school`. School resources subclass `TenantScopedViewSet` / `TenantAPIView`; guard tests fail if a route skips them or an isolation case is missing.
- Role → permission registry in `apps/accounts/roles.py`; the frontend receives the caller's permissions from `/auth/me`.

### School lifecycle, dashboards, audit logs (Phase 3)
- Super Admin: `POST /platform/schools/{id}/suspend|deactivate|reactivate/` with `{reason, confirm: true}`. Nothing is deleted; the school's users get `403 school_disabled`.
- Platform dashboard, school list/detail (Users and Activity tabs, audited), platform and school audit logs.
- School Admin: profile, dashboard, users, activity.

### SaaS billing (Phase 4)
- **Plans are data** (`/platform/plans/`). No prices in code. `seed_plans` is development seed data only. Public pricing data: `GET /api/v1/plans/`.
- **Platform settings** (`/platform/settings/`): `trial_duration_days` (7), `trial_expiring_notice_days` (2), `expiring_notice_days` (7), `past_due_grace_days` (5), `expired_access_mode` (`READ_ONLY` | `BLOCKED`), `trial_plan_slug`.
- **State machine, no scheduler.** `effective_state()` computes TRIALING / ACTIVE / PAST_DUE / EXPIRED / CANCELLED / SUSPENDED from timestamps. A SQL `CASE` twin powers lists and filters, and a test asserts both agree for every combination.
- **Access:** FULL (trial, active, grace period, cancelled until period end), READ_ONLY (expired: viewing and exports work, writes return `402 subscription_expired`), BLOCKED (suspended subscription, or expired with mode `BLOCKED`: `403 subscription_blocked`).
- **Manual payments** (`/platform/payments/`): bank transfer, JazzCash, Easypaisa, cash, other. Recording a payment activates or renews the subscription (new period starts at `max(end_date, now)` and lasts N calendar months), is atomic, rejects duplicate method + reference, and is append-only. `gateway` / `gateway_payload` are the hook for a future gateway.
- **Super Admin actions** (`/platform/subscriptions/{id}/…`): `extend-trial`, `extend`, `change-plan`, `cancel`, `suspend`, `resume`, plus `events/` history. The School Admin gets no billing controls, only notifications and a banner.
- **Notifications** (`/api/v1/notifications/`): stored in PostgreSQL, created lazily on `/auth/me`, the notification endpoints and request-time sync, idempotent through a `dedupe_key` partial unique constraint. Billing and lifecycle notices go to School Admins only. A suspended school's admin can still read them.
- Existing schools from earlier phases receive a trial through the `0002_backfill_trials` data migration.

### API summary
```
auth/        csrf · register · login · logout · refresh · me · change-password · password-reset/request|confirm
school/      profile · dashboard · users[/{id}] · audit-logs[/{id}]
notifications/  · unread-count · {id}/read · mark-all-read
plans/       (public)
platform/    dashboard · settings · schools[/{id}] (+users, activity, suspend, deactivate, reactivate, notify)
             plans[/{id}] · subscriptions[/{id}] (+actions, events) · payments[/{id}] · audit-logs (+actions)
```

---

# Poora usage guide aur manual test script

Ye script upar se neeche **order mein** chalayein: har step ke baad data agle step mein kaam aata hai. Har line ke aage `Expected` wo hai jo dikhna chahiye. Agar kuch alag dikhe to wahi bug hai: step number aur screenshot/terminal output bhej dein.

## 0. Tayyari (ek baar)

Do terminals chahiye (dono PowerShell):

```powershell
# Terminal 1: backend
cd "D:\My personal projects\school-saas\backend"
.venv\Scripts\Activate.ps1
python manage.py makemigrations
python manage.py migrate
python manage.py bootstrap_school_defaults
python manage.py check_rls
python manage.py createsuperuser        # platform owner (apni email + strong password, 10+ chars)
python manage.py seed_plans             # sample plans (sirf testing ke liye)
python manage.py runserver              # http://localhost:8000/api/v1/health/?db=1

# Terminal 2: frontend
cd "D:\My personal projects\school-saas\frontend"
npm run dev                             # http://localhost:3000
```

- [ ] `http://localhost:8000/api/v1/health/?db=1` mein `"database": "ok"` aaye.
- [ ] `http://localhost:3000` khulne par `/login` par redirect ho aur page styled ho.
- Emails development mein **backend terminal** mein print hoti hain (welcome, password reset link, notices). Link wahin se copy karein.

**Testing ke liye 2 browsers/profiles rakhein** (maslan Chrome normal + Incognito), taake do users ek saath login rakh sakein. Cookies shared hoti hain, is liye ek hi window mein do users nahi chalte.

### Test accounts ka plan

| Role | Email (misaal) | Kaise banta hai |
|---|---|---|
| Super Admin | `root@platform.test` | `createsuperuser` |
| School Admin A | `admin.a@test.com` | `/register` (School A) |
| School Admin B | `admin.b@test.com` | `/register` (School B, isolation test ke liye) |
| Teacher, Accountant, Receptionist | `teacher@a.test`, `acc@a.test`, `reception@a.test` | School A: Settings → Users → Add user |
| Parent, Student | `parent@a.test`, `student@a.test` | Settings → Users, phir **section 5.3** ka link step |

Password kam az kam 10 characters. Admin ke banaye users ko "Temporary password" milta hai, pehle login par **password change karna lazmi** hai.

---

## 1. Platform (Super Admin)

`root@platform.test` se login karein, `/platform/dashboard` khulna chahiye.

- [ ] Dashboard: schools, users, **Students/Teachers** (abhi 0), subscriptions ke cards dikhen.
- [ ] **Plans** → seeded plans (Basic/Standard/Pro) dikhen. "New plan" se `Tiny` plan banayein: max students = 2, max teachers = 1, max classes = 2 (limit wale fields jo bhi dikhen).
- [ ] **Settings**: `trial_duration_days` dekhein (default 7), `expired_access_mode` (READ_ONLY ya BLOCKED), `school_image_quota_mb` (50). Abhi koi value na badlein.
- [ ] **Audit logs**: filhal khali ya sirf login events.
- [ ] Wrong role check: Super Admin ko `/dashboard` (school page) kholne par redirect/forbidden mile.

## 2. School register + onboarding (School A)

Incognito window mein `http://localhost:3000/register`.

- [ ] Form: school name `Green Valley School`, admin name, email `admin.a@test.com`, phone, password (10+ chars), country, city. Submit → **dashboard** khule.
- [ ] Backend terminal mein **welcome email** print ho.
- [ ] Dashboard par "Getting started" checklist (profile, team, classes, teachers, students) sab pending.
- [ ] Subscription banner: **trial** chal raha hai (7 din).
- [ ] Validation: dobara usi email se register → "email already exists". Kamzor password (`short`) → reject. Khali school name → reject.
- [ ] Rate limit: ek hi machine se 5 se zyada registrations/ghanta → "too many requests".
- [ ] Settings → **School profile**: phone aur address bharein, save → dashboard checklist ka "profile" item tick ho.

## 3. Login, logout, password (sab roles par)

- [ ] Galat password se login → generic error (ye na bataye ke email maujood hai ya nahi).
- [ ] **Ek hi email se 5 galat attempts** → 6th par "too many attempts, 15 minute baad try karein". (Lockout test ke baad us email ko 15 min chhor dein ya doosre user se kaam karein.)
- [ ] "Forgot password?" → email dalein → backend terminal mein reset link → link kholen → naya password → login ho. Wahi link dobara use karein → reject (single-use). 30 minute baad link expire.
- [ ] Unknown email par bhi forgot-password wahi generic message de.
- [ ] Logout → back button se protected page kholne ki koshish → `/login` par bhej de.
- [ ] Browser DevTools → Application → Cookies: `access_token` aur `refresh_token` **HttpOnly** hon (JavaScript se nazar nahi aate). `localStorage` mein koi token na ho.
- [ ] 15 minute baad (access token expiry) page refresh karne par user logout na ho (refresh token khud naya access le).

## 4. Users banana (School Admin A)

Settings → **Users** → Add user. Ye users banayein: Teacher, Accountant, Receptionist, Parent, Student (emails upar table se, temporary password `Temp-Pass-12345`).

- [ ] Har user list mein dikhe, role sahi.
- [ ] Doosre browser mein har user se login → **pehle change-password page** aaye; naya password dene ke baad hi dashboard.
- [ ] Edit user: naam/role badlein, save. User ko **deactivate** karein → wo login na kar sake; reactivate karne par kar sake.
- [ ] Admin apne aap ko deactivate/downgrade na kar sake (error aaye).
- [ ] Settings → **Activity**: user create/update events audit log mein dikhen.

## 5. Academics setup (School Admin A)

### 5.1 Session, classes, sections
- [ ] **Classes → Sessions**: registration par ek **current** session (is saal ka) pehle se maujood ho.
- [ ] Naya session `2027` (1 Jan 2027 – 31 Dec 2027) banayein, "current" tick **na** karein. Duplicate name `2027` dobara → error (409). End date start se pehle → error.
- [ ] **Classes tab**: class `9` (order 9), `10` (order 10) banayein.
- [ ] **Sections tab**: `9-A` (capacity 2), `10-A` (capacity 30), `10-B` banayein. Doosre school ki class select nahi ho sakti (dropdown mein sirf apni).
- [ ] Plan limit: (section 12 mein dobara) class limit test.

### 5.2 Subjects
- [ ] **Subjects**: `Mathematics (MTH)`, `Urdu (URD)`, `English (ENG)`. Code duplicate (`mth` dobara) → error.
- [ ] **Subjects by class** tab: class 10 ko Math, Urdu, English assign karein; ek ko "Optional" mark karein.

### 5.3 Teachers
- [ ] **Teachers → Add teacher**: `Sana Ali`, gender, phone, qualification. **Sign-in account** dropdown mein `teacher@a.test` select karein (isi se teacher login se wapas apne data tak pahunchta hai). Employee ID khud `EMP-0001` bane.
- [ ] **Assignments** tab: Sana → section `10-A` → subject `Mathematics`. Ek aur: Sana → `10-A` → subject khali (sab subjects) + "Class teacher" tick. Same assignment dobara → error (409).
- [ ] Timetable (section 6.4 mein).

> **Parent/Student login ko data se jodna.** Ab UI se hota hai (School Admin): **Students → Guardians tab → guardian ko Edit → "Parent's sign-in account"** (parent user chunein), aur **student ko Edit → "Student's sign-in account"**. Ye step section 6 ke baad karein. (Shell wala purana tareeqa ab zaroori nahi.)

## 6. Students, guardians, enrollment (School Admin A)

### 6.1 Admission
- [ ] **Students → Admit student**: 4 students banayein (Ali, Bilal, Chand, Danish). Photo upload karein (PNG/JPG/WEBP). Numbers `STU-00001`, `STU-00002`... **khud** bane.
- [ ] Validation: future date of birth, galat phone (`call me`), galat email → field par error.
- [ ] Bohat bada ya image na hone wali file photo mein → client error ya server reject.
- [ ] List: search (naam/number), status filter, class/section filter. CSV aur PDF buttons.

### 6.2 Guardians
- [ ] Student kholein → **Guardians** tab → "Add new guardian" (father, phone `+92 300 1111111`, relationship Father, Primary). Doosre student par "Link existing guardian" (wahi guardian, mother se alag).
- [ ] Wahi guardian dobara link karein → error. Primary doosre ko dein → pehla "Primary" na rahe.
- [ ] Unlink → guardian record bacha rahe.

### 6.3 Enrollment
- [ ] Ali, Bilal, Chand ko **Enroll** → section `9-A` (capacity 2): Ali roll 1, Bilal roll 2, **Chand → error "section full"**.
- [ ] Chand ko `10-A` mein enroll karein (roll auto 1). Danish `10-A` (roll 2). Dono ko `10-A` mein rakhein.
- [ ] Ali ko "Change section" se `10-B` mein bhejein → class bhi 10 ho jaye.
- [ ] Student profile par Edit, Change status (Transferred) → enrollment band ho, class "Not enrolled". Dobara Active karein aur enroll karein.
- [ ] Delete student → list se gayab; (data soft-delete hota hai, invoices/marks nahi mitte).
- [ ] Certificate button (student enrolled ho) → PDF download.

### 6.4 Timetable
- [ ] **Timetable** → section `10-A` → khali cell par "+" → Math, Sana, Monday, period 1, 08:00–08:40.
- [ ] Wahi teacher usi period par `10-B` mein → **clash error**. Doosra period → OK. End time start se pehle → error.
- [ ] Teacher (`teacher@a.test`) ko login karwa ke dekhein: sirf apni classes ki timetable.

## 7. Attendance

**Admin/Teacher se (Attendance → Mark attendance):**
- [ ] Section `10-A`, aaj ki date → roster aaye → "Mark all present", ek ko Absent, ek ko Late → Save → "Attendance saved".
- [ ] Wapas aa kar wahi date kholein → marks pre-filled; badal kar dobara save → duplicate nahi bante.
- [ ] Future date nahi chuni ja sakti (max aaj).
- [ ] **Teacher login:** sirf apni assigned section ka roster mil sake; `9-A` (assigned nahi) par error/403. 7 din se purani date par teacher edit na kar sake (admin kar sake).
- [ ] **Monthly report** tab: section + month → present/absent/late/leave aur **%** (late = attended, leave excused). PDF/CSV download.
- [ ] **Teachers tab** (admin/receptionist): teachers ki aaj ki attendance mark karein. Teacher/accountant ko ye tab na dikhe.
- [ ] Dashboard par "Today's attendance %" real numbers dikhaye.

## 8. Exams aur results

### 8.1 Setup (Admin)
- [ ] **Exams → Grading scales**: default "Standard" (A+ … F) maujood. Naya scale banayein jisme ranges **overlap** karein → error. Theek ranges → save.
- [ ] **Exam types**: Monthly Test/Midterm/Final maujood.
- [ ] **Exams** tab → Add exam: `Midterm 2026`, session current, type Midterm.
- [ ] Exam kholein → **Schedule** tab: class 10 ke liye Math (total 100, passing 33) aur Urdu (50, 20) add karein.
- [ ] Bina subject ke naya exam "Schedule exam" karein → error. Subjects ke saath → status **Scheduled**.

### 8.2 Marks entry
- [ ] **Teacher login** → Exams → exam → **Marks entry** → Mathematics → apne section ke students dikhen → marks 80, 80, 30 → Save.
- [ ] Urdu select karna chahein to error/403 (Sana sirf Math ke liye assigned; "sab subjects" wali assignment ki wajah se agar Urdu allow ho jaye to wo bhi theek hai kyunke 5.3 mein dono assignments hain, iss liye Urdu test ke liye ek aur teacher banayein jo sirf Math le).
- [ ] Total se zyada ya negative marks → reject. "Absent" tick → marks disable. Cell khali = mark clear.
- [ ] Exam status khud **Marks entry** ho jaye.
- [ ] Admin Marks tab se Urdu ke marks 40, 40, 45 dalein.

### 8.3 Preview aur publish (Admin)
- [ ] **Results** tab: live preview — % , grade, position, Pass/Fail. Chand (Math 30 < 33) **Fail**.
- [ ] Ek student ke marks adhure chhor kar "Publish results" → **"marks missing"** confirm dialog; "Publish anyway (absent)" tick kiye bina button disabled.
- [ ] Sab marks bharein → Publish → status **Published**; analysis (pass rate, subject averages) dikhe.
- [ ] **Results** page (sidebar): report cards, position (tie par same position), PDF download, card kholein → Print.
- [ ] Teacher results-publish na kar sake (button/endpoint 403).
- [ ] **Recompute:** Grading scale edit karein (grades badlein) → exam par "Recompute & republish" → report cards ke grades naye. Pehle wale published results republish se pehle tak purane rahein.
- [ ] Published exam par subject schedule edit/delete na ho (locked). Sirf Draft exam delete ho.
- [ ] Archive → status Archived.

## 9. Fees

### 9.1 Setup
- [ ] **Fees → Categories**: defaults (Tuition, Admission, Exam, Transport) maujood; apni category add karein.
- [ ] **Fee structures → New**: `Monthly Class 10`, session current, class 10, Monthly, items: Tuition 5000 + Exam Fee 500 (total 5500 dikhe). Same category do baar → error.

### 9.2 Invoices
- [ ] **Invoices → Generate invoices**: structure, period `Oct-2026`, due date → "N invoice(s) created". **Dobara chalayein** → 0 created, N skipped (idempotent).
- [ ] Numbers `INV-00001…` ek ke baad ek. Due date issue date se pehle → error.
- [ ] Invoice kholein: discount **10%** (550) aur **Fixed 250**, fine 100 → total = 5500 − 800 + 100 = **4800**.
- [ ] Discount jo total ko negative kare → reject.

### 9.3 Payments
- [ ] **Record payment** 1000 cash → receipt `RCT-00001`, status **Partially paid**, balance 3800.
- [ ] Balance se zyada, 0, negative, future date → reject.
- [ ] Baqi paise de do → **Paid**, balance 0. Receipt PDF download.
- [ ] **Reverse** (Payments tab/invoice page): reason ke saath → balance wapas, status wapas Issued/Partially paid. Dobara reverse → error.
- [ ] **Void:** payment wale invoice par error ("reverse first"); payment reverse karne ke baad void ho. Void invoice par payment/fine/discount na lage. Void ke baad usi period ka naya invoice generate ho sake.
- [ ] Filters: status, "Overdue only" (due date guzri hui), search.
- [ ] **Roles:** Receptionist payment record kare lekin Generate/Reverse/Void na kar sake. Accountant sirf **apni aaj ki** payment reverse kare (kisi aur ki ya purani par 403); Admin sab reverse kare. Teacher ko Fees menu hi na dikhe.

## 10. Reports aur exports

- [ ] **Reports** page: Students summary (class/section counts), Outstanding fees (total + list), Attendance (section+month → PDF), Exam analysis.
- [ ] CSV downloads: students, teachers, attendance, fees, results. Excel mein kholein: pehle column theek, naam Urdu ho to bhi sahi.
- [ ] **Formula injection:** ek student ka first name `=HYPERLINK("http://evil")` rakhein → CSV mein `'=HYPERLINK...` (apostrophe ke saath) aaye.
- [ ] PDFs: report card, transcript, receipt, invoice, certificate, student list, outstanding fees. (PDF mein Urdu naam sahi nahi dikhenge: sirf Latin font.)
- [ ] 20,000+ rows ya 500+ PDF rows par "narrow filters" error (413), automated tests mein covered.
- [ ] Settings → Activity mein har export ka "EXPORT_GENERATED" event.
- [ ] Teacher: students/teachers CSV na mile; attendance/results CSV sirf apni sections ki.

## 11. Announcements, notifications, email

- [ ] **Announcements → New** (Admin): audience Everyone, pinned → sab roles ko dikhe (Pinned upar).
- [ ] Audience Parents → sirf parent (aur admin) ko; Teachers → teachers ko; Staff → admin/teacher/accountant/receptionist; **One class** (class 10) → us class ke teacher/parent/student ko.
- [ ] Teacher: sirf **apni class** ke liye post kar sake, "Everyone" par 403; kisi aur ki post edit na kare.
- [ ] Expiry past ki ho to non-admin ko na dikhe. "New" badge, "Mark as read" → badge hat jaye.
- [ ] **Notifications** (bell): subscription/payment events; read mark karein.
- [ ] Emails (backend terminal): welcome, password reset, payment confirmation, trial/subscription expiry notices.

## 12. Subscription lifecycle aur plan limits

### 12.1 Plan limits
- [ ] Platform → Schools → School A → Subscription: plan **Tiny** set karein (payment record karke ya subscription edit se).
- [ ] School A: teesra student admit karne par **"plan limit reached"** (403). Doosri class ke baad teesri class bhi block.
- [ ] Plan upgrade karte hi dobara allowed.

### 12.2 Trial expiry / read-only / blocked
Expiry time-based hai, is liye shell se jaldi simulate karein:
```powershell
python manage.py shell
```
```python
from datetime import timedelta
from django.utils import timezone
from apps.subscriptions.models import Subscription
Subscription.objects.filter(school__name="Green Valley School").update(
    trial_end=timezone.now() - timedelta(days=1))
exit()
```
- [ ] School A admin ko ek request ke baad **"trial ended"** banner/notification + email.
- [ ] `expired_access_mode = READ_ONLY` (Platform Settings): data **dikhe**, par koi create/edit/delete **402** ("subscription expired").
- [ ] `BLOCKED` karein: school pages blocked (403), login ho par kaam na ho.
- [ ] Platform → School → **Record payment** (cash, 1 month, plan) → school ka access foran wapas, payment confirmation email.
- [ ] Platform payments list mein entry aur audit log.

### 12.3 School lifecycle (Super Admin)
- [ ] School A ko **Suspend** (reason + confirm) → School A ke users `/suspended` page dekhen, login ke baad kuch na khul sake.
- [ ] **Reactivate** → sab wapas. **Deactivate** bhi aise hi. Galat transition (jaise already suspended ko dobara suspend) → 409.

## 13. Security aur tenant isolation (sab se zaroori)

School B register karein (`admin.b@test.com`, doosri incognito/profile) aur School A ka data copy kar ke kholne ki koshish karein:

- [ ] School A ke student ka URL (`/students/<id>`) School B admin ke browser mein kholein → **Not found / error**, data nahi.
- [ ] Wahi UUID API par: `http://localhost:3000/api/v1/school/students/<id>/` School B ke login ke saath → **404** (kabhi 200 nahi).
- [ ] School B ki dropdowns mein School A ki class/section/teacher kabhi na aaye.
- [ ] School B mein student ka sign-in account/guardian School A ke user se link karne ki koshish → "does not exist".
- [ ] School B ka export CSV School A ke naam/invoice number na rakhe.
- [ ] **CSRF:** DevTools/Postman se bina `X-CSRF-Token` header ke koi POST/PATCH/DELETE → 403.
- [ ] Parent apne bachay ke siwa kisi bachay ka invoice/result/attendance na dekhe (URL badal kar try karein: 404).
- [ ] Student sirf apna data dekhe. Parent/Student koi create/edit button na dekhe.
- [ ] `python manage.py check_rls` → "All public tables have RLS enabled."

## 14. Role matrix (har role se login kar ke tick karein)

| Kaam | Admin | Teacher | Accountant | Receptionist | Parent | Student |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Students dekhna | sab | apne sections | sab | sab | apne bachay | khud |
| Student admit/edit | ✔ | ✘ | ✘ | ✔ | ✘ | ✘ |
| Student delete/status | ✔ | ✘ | ✘ | ✘ | ✘ | ✘ |
| Attendance mark | ✔ | apne sections | ✘ | ✘ | ✘ | ✘ |
| Teacher attendance | ✔ | ✘ | ✘ | ✔ | ✘ | ✘ |
| Marks entry | ✔ | apne subject/section | ✘ | ✘ | ✘ | ✘ |
| Results publish | ✔ | ✘ | ✘ | ✘ | ✘ | ✘ |
| Results dekhna | sab | apne sections | sab | sab | apne bachay | khud |
| Fees generate/discount/void | ✔ | ✘ | ✔ | ✘ | ✘ | ✘ |
| Payment record | ✔ | ✘ | ✔ | ✔ | ✘ | ✘ |
| Payment reverse | ✔ | ✘ | apni, aaj ki | ✘ | ✘ | ✘ |
| Fees dekhna | sab | ✘ | sab | sab | apne bachay | khud |
| Exports | sab | attendance, results | fees | students | ✘ | ✘ |
| Announcement post | sab audiences | apni class | ✘ | ✘ | ✘ | ✘ |
| Settings/Users | ✔ | ✘ | ✘ | ✘ | ✘ | ✘ |

## 14b. Naye features ka test script

### Parent/Student ko jodna aur parent ka view
- [ ] Students → **Guardians** tab: guardian ko Edit → "Parent's sign-in account" mein `parent@a.test` → Save. List mein "Linked" badge.
- [ ] Student ko Edit → "Student's sign-in account" → `student@a.test`.
- [ ] `parent@a.test` se login (doosra browser): sirf apne bachay ke attendance/fees/results; baqi 404.

### Documents, guardians list, ID cards
- [ ] Student → **Documents** tab: "B-Form" add/edit/delete (sirf record, file nahi).
- [ ] Student → **ID card** button → CR80 size PDF (photo, naam, ID, class). Bina enrollment wale student par error.
- [ ] Students list → section filter chuniye → **ID cards (section)** → A4 sheet (2 x 5 cards). Parent ko ye button/endpoint na mile (403).

### CSV import (Students aur Teachers)
- [ ] Students → **Import CSV** → "Download template" → Excel mein kuch rows bharein (CSV UTF-8) → **Check file**: sab theek ho to "N ready to import".
- [ ] Jaan bujh kar ghalat rows rakhein (galat gender, future date of birth, nahi maujood section, section capacity se zyada, file mein duplicate, pehle se maujood student): har row ka masla **row number ke saath** dikhe aur **Import** button na aaye.
- [ ] Theek file → **Import** → students, guardians (ek hi phone par siblings ka ek guardian) aur enrollments ban jayen; student numbers `STU-0000N` khud.
- [ ] Plan limit (Tiny plan) se zyada rows → poori file reject (403), kuch save nahi.
- [ ] 500 se zyada rows ya 1 MB se bari file → reject. Teachers → Import CSV isi tarah (Employee IDs `EMP-000N`).

### Parents ko alerts aur fee reminders
- [ ] Parent account guardian se linked ho. Attendance mein uske bachay ko aaj **Absent** mark karein → parent ki **bell/Notifications** mein "… was marked absent" (ek hi dafa, dobara save par duplicate nahi). Backend terminal mein email.
- [ ] Guzishta date par absent mark → alert nahi (sirf aaj ke liye).
- [ ] Fees → Invoices → **Send reminders** (Overdue ya Due soon) → "N matched, X notified, Y without a parent account". Dobara usi din → 0 notified (dedupe). Receptionist/teacher ko ye button na mile.
- [ ] Invoice page par **WhatsApp reminder** aur Reports → Outstanding fees mein har row par **WhatsApp**: apna WhatsApp prefilled message ke saath khule (number `03xx...` ho to khud `92` laga deta hai).

### Year-end promotion
- [ ] Naya session + naye classes/sections banayein. **Classes → Year-end** tab: from session, into session, section chunein, har student ka Promote/Repeat/Graduate, target sections → Process.
- [ ] Natija: purani enrollments Promoted/Repeated/Graduated, naye session mein nayi enrollments, Graduate wale students ka status Graduated. Dobara usi section par → error (already processed). Teacher ko tab na dikhe.

### Logo aur report card remarks
- [ ] Settings → School profile → **School logo** upload (resize khud); Remove logo. Doosre school ka logo URL kholne par 404.
- [ ] Results → report card kholein: Teacher login se sirf apne section ke bachay par **Teacher's remarks**; "Principal's remarks" sirf admin ko. Save ke baad PDF mein dono remarks.
- [ ] Teacher History: Attendance → **Teacher history** tab (date range).

## 15. Automated tests

```powershell
cd backend
.venv\Scripts\Activate.ps1
python manage.py test                                   # sab (Postgres chalu hona chahiye)
python manage.py test apps.core                         # isolation matrix, route guards, N+1, source guards
python manage.py test apps.students apps.academics      # students, enrollment, promotion, timetable
python manage.py test apps.attendance apps.examinations apps.fees apps.reports
python manage.py test apps.notifications                # announcements + email
python manage.py test apps.core.tests.test_isolation_matrix -v 2
```

Frontend:
```powershell
cd frontend
npm run lint
npx tsc --noEmit
npm run build
```

Failure aaye to **poora traceback** (pehla error se shuru) bhej dein. Ek bug aksar kai tests ko tora deta hai, is liye pehla failure sab se zaroori hai.

## 16. Jo abhi project mein nahi hai

- **Asli WhatsApp/SMS bhejna:** system khud message nahi bhejta (provider ki API key aur approval chahiye). Iski jagah **WhatsApp click-to-chat links** hain (invoice page aur Reports mein): button dabane par aap ka apna WhatsApp prefilled message ke saath khulta hai.
- **Online payment gateway** (JazzCash/Easypaisa/card): merchant account chahiye; abhi payments manually record hoti hain.
- **Mobile app, Urdu interface, PDF mein Urdu naam** (Latin font).
- **Library, transport routes, hostel, payroll modules.**
- Email abhi console (backend terminal) par hai; asli bhejne ke liye `EMAIL_BACKEND=smtp` (`docs/DEPLOYMENT.md`).

## 17. Aam masail

| Masla | Hal |
|---|---|
| Page unstyled | `postcss.config.mjs` + `@tailwindcss/postcss` (Tailwind v4), phir `.next` delete |
| `ERESOLVE` npm par | `node_modules` + `package-lock.json` delete, `eslint-config-next` = next ka version |
| Login ke baad hamesha logout | `.env`/`.env.local` mein `BACKEND_ORIGIN` aur `PROXY_SHARED_SECRET` dono taraf barabar |
| API 403 "CSRF" | Browser se hi chalayein (proxy header lagata hai); Postman mein `X-CSRF-Token` + cookie dein |
| `makemigrations` ke baad bhi table missing | `python manage.py migrate`; phir `check_rls` |
| `relation ... does not exist` tests mein | Test DB banne ke liye `makemigrations` pehle chalayein |
| Photo upload reject | PNG/JPEG/WEBP, 512 px tak, ~150 KB tak (browser khud chhota karta hai) |
| 402 "subscription expired" | Platform → School → Record payment ya trial_end reset |
| 429 too many requests | 15 min intezar ya doosra email/IP |
