# Plan B: explicit Python entrypoint (only if Vercel does not detect Django)

The normal setup needs none of this: Vercel detects `backend/manage.py` and serves `config.wsgi.application`.
Use these two files **only** if the backend deployment shows no function / `404: NOT_FOUND` for every URL even
though the build succeeded.

1. Create `backend/api/index.py` from `index.py` in this folder.
2. Create `backend/vercel.json` from `vercel.json` in this folder (it sends every URL to that function).
3. In Vercel: backend project -> Settings -> Build and Deployment -> Framework Preset = **Other**. Redeploy.

Do not keep both setups at once (the rewrite would point at a function that the Django preset does not create).
