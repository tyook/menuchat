# CI/CD Design: GitHub Actions + Vercel + Render

**Date:** 2026-02-20
**Status:** Draft

## Overview

CI pipeline via GitHub Actions. Frontend (Next.js) deployed to Vercel, backend (Django) deployed to Render. Two environments: staging and production.

## Environments

| Environment | Frontend (Vercel) | Backend (Render) | Trigger |
|---|---|---|---|
| **Staging** | `menuchat-staging` Vercel project | `menuchat-staging` Render web service | Push to `main` (auto-deploy) |
| **Production** | `menuchat-production` Vercel project | `menuchat-production` Render web service | Git tag `v*` or manual workflow dispatch |

## CI Pipeline

**File:** `.github/workflows/ci.yml`
**Trigger:** Pull requests targeting `main`

### Backend Job

- Ubuntu latest, Python 3.12
- PostgreSQL 16 + Redis 7 service containers
- Install dependencies via Poetry
- `ruff check` + `ruff format --check`
- `pytest`

### Frontend Job

- Ubuntu latest, Node 20
- Install dependencies via Yarn
- `yarn lint`
- `yarn build`

Both jobs run in parallel. PR cannot merge unless both pass.

## CD — Staging

**Trigger:** Push to `main` (after PR merge)

Both Vercel and Render handle staging deploys natively via their GitHub integrations — no GitHub Actions workflow needed.

- **Frontend:** Vercel `menuchat-staging` project is linked to `main` branch with auto-deploy enabled.
- **Backend:** Render `menuchat-staging` web service is linked to `main` branch with auto-deploy enabled. Render builds via Docker, runs migrations, and restarts.

## CD — Production

**File:** `.github/workflows/deploy-production.yml`
**Trigger:** Git tag push matching `v*` OR manual `workflow_dispatch`

### Frontend (Vercel)

- GitHub Actions runs `vercel --prod` using the Vercel CLI
- Uses `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` from GitHub secrets
- Production Vercel project has auto-deploy **disabled**

### Backend (Render)

- GitHub Actions triggers a deploy via Render Deploy Hook (`curl` to webhook URL)
- Deploy hook URL stored as `RENDER_DEPLOY_HOOK_PRODUCTION` GitHub secret
- Render builds from latest `main`, runs migrations, and restarts
- Production Render service has auto-deploy **disabled**

## Required GitHub Secrets

| Secret | Purpose |
|---|---|
| `VERCEL_TOKEN` | Vercel API token for production frontend deploys |
| `VERCEL_ORG_ID` | Vercel team/org ID |
| `VERCEL_PROJECT_ID` | Production Vercel project ID |
| `RENDER_DEPLOY_HOOK_PRODUCTION` | Render deploy hook URL for production backend |

## One-Time External Setup

1. **Vercel** — create `menuchat-staging` and `menuchat-production` projects. Link staging to `main` branch. Disable auto-deploy on production.
2. **Render** — create `menuchat-staging` and `menuchat-production` web services. Link staging to `main` with auto-deploy on. Disable auto-deploy on production. Create a deploy hook for production.
3. **GitHub** — add secrets listed above to repository settings.
4. **Ruff** — add `ruff.toml` config to backend.

## Environment Variables

Each environment gets its own set of env vars configured in the respective dashboards (not in GitHub Actions):

- **Vercel dashboard:** `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL`, etc.
- **Render dashboard:** `DATABASE_URL`, `REDIS_URL`, `DJANGO_SECRET_KEY`, `STRIPE_SECRET_KEY`, `OPENAI_API_KEY`, etc.
