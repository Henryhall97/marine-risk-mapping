# Deployment Guide — Marine Risk Mapping (v1)

> **Goal:** Get the platform reachable at a public URL in a few hours.
>
> **Architecture:**
> ```
> Vercel (Next.js)  ──► api.<domain>  ──►  Caddy → FastAPI → PostGIS
>                          (HTTPS)         (single Docker host)
> ```

## Cost estimate

| Service | Spec | $/mo |
|---|---|---|
| Hetzner CCX23 (Frankfurt or Ashburn) | 4 vCPU, 16 GB RAM, 160 GB SSD | ~€30 |
| Domain (Cloudflare) | api subdomain | ~$10/yr |
| Vercel Hobby | Next.js frontend | $0 |
| **Total** | | **≈ $35/mo** |

DigitalOcean equivalent (4 vCPU / 16 GB Premium Intel) is ~$84/mo. AWS
EC2 t3.xlarge + RDS would be ~$200/mo. Hetzner is the sweet spot.

---

## 1. Prepare the database dump (local)

Trim the 81 GB local DB to ~3 GB compressed by exporting only API-required tables:

```bash
# From project root with Docker postgis container running:
./scripts/dump_prod_db.sh
# → ./db_dumps/marine_risk_prod_<YYYYMMDD>.dump
```

Verify size:

```bash
ls -lh db_dumps/
```

Expect 2–4 GB. If much larger, a non-API table is included — audit `scripts/dump_prod_db.sh`.

---

## 2. Provision the VM

**Hetzner Cloud (recommended):**

1. Sign up → create a new project → "Add Server"
2. Image: **Ubuntu 24.04**
3. Type: **CCX23** (or CX42 if cost is critical: 4 vCPU / 16 GB / shared, ~€15/mo)
4. Networking: enable IPv4 + IPv6
5. SSH key: paste your `~/.ssh/id_ed25519.pub`
6. Note the public IPv4 (e.g. `49.12.34.56`)

**DNS (registrar / Cloudflare):**
- Add A record: `api.whalewatch.uk` → `49.12.34.56`
- Wait for propagation (usually <1 min on Cloudflare, ~5 min on most registrars).
- Verify: `dig +short api.whalewatch.uk`

---

## 3. Server bootstrap

One command does everything (installs Docker, configures firewall, clones repo):

```bash
ssh root@49.12.34.56
curl -fsSL https://raw.githubusercontent.com/Henryhall97/marine-risk-mapping/main/scripts/bootstrap_vm.sh | bash
```

When it finishes you'll be in `/opt/marine-risk-mapping` with Docker installed, firewall configured, and the repo cloned.

---

## 4. Configure environment

```bash
cp .env.prod.example .env
nano .env
```

Fill in:
- `POSTGRES_PASSWORD` — `openssl rand -base64 32`
- `MR_JWT_SECRET` — `openssl rand -hex 32`
- `MR_CORS_ORIGINS` — `https://whalewatch.uk,https://www.whalewatch.uk` (add the Vercel preview URL too once deployed)
- `DOMAIN` — `api.whalewatch.uk`

---

## 5. Upload the database dump

From your **local** machine:

```bash
mkdir -p ~/upload && cp db_dumps/marine_risk_prod_*.dump ~/upload/
scp -C ~/upload/marine_risk_prod_*.dump \
    root@49.12.34.56:/opt/marine-risk-mapping/db_dumps/
```

3 GB over a 50 Mbps connection ≈ 8 minutes.

---

## 5b. Upload static assets + ML models

The backend image **does not** bake in the ML classifiers, and the frontend **does not** bundle the whale GLBs / species photos / wizard images (gitignored due to size + copyright). They live on the host and are bind-mounted / served by Caddy.

From your laptop, project root:

```bash
scripts/upload_assets.sh root@49.12.34.56
```

This rsyncs (totals ~580 MB):

| Source (local) | Destination (VM) | Served via |
|---|---|---|
| `frontend/public/models/` | `/opt/marine-risk-mapping/frontend/public/models/` | Caddy `/static/models/*` |
| `frontend/public/species/` | `…/frontend/public/species/` | Caddy `/static/species/*` |
| `frontend/public/wizard/` | `…/frontend/public/wizard/` | Caddy `/static/wizard/*` |
| `data/processed/ml/photo_classifier/` | `…/data/processed/ml/photo_classifier/` | Bind-mounted into `backend` container |
| `data/processed/ml/audio_classifier/` | `…/data/processed/ml/audio_classifier/` | Bind-mounted into `backend` container |

The Vercel build picks up the asset URLs automatically via `next.config.ts` rewrites — `/models/foo.glb` on the frontend transparently fetches `https://api.whalewatch.uk/static/models/foo.glb`.

---

## 6. Start Postgres and restore

```bash
# On the VM:
cd /opt/marine-risk-mapping
docker compose -f docker/docker-compose.prod.yml up -d postgis

# Restore (helper script handles waiting + sanity checks)
bash scripts/restore_prod_db.sh
```

Expect ~5–10 minutes for the restore. The script prints row counts for `fct_collision_risk` (~1.8M), `fct_collision_risk_seasonal` (~7.3M), `macro_risk_overview` (~70K), and `species_crosswalk` (138) when finished.

---

## 7. Build and start the backend + Caddy

```bash
docker compose -f docker/docker-compose.prod.yml up -d --build

# Tail logs to confirm health
docker compose -f docker/docker-compose.prod.yml logs -f backend caddy
```

Caddy will auto-issue a Let's Encrypt cert for `$DOMAIN` on first request (takes ~30 s).

Test from your laptop:

```bash
curl https://api.whalewatch.uk/health
# → {"status":"ok"}
curl 'https://api.whalewatch.uk/api/v1/risk/zones?lat_min=40&lat_max=41&lon_min=-71&lon_max=-70&limit=5'
curl 'https://api.whalewatch.uk/api/v1/species' | head -c 500
```

---

## 8. Deploy frontend to Vercel

```bash
# Local: from project root
cd frontend
npx vercel  # → follow prompts to link the project
```

Or via the Vercel UI:
1. Import the repo `Henryhall97/marine-risk-mapping`
2. **Framework preset:** Next.js
3. **Root directory:** `frontend`
4. **Environment variable:**
   `NEXT_PUBLIC_API_URL` = `https://api.whalewatch.uk`
5. Deploy.
6. **Custom domain:** Project Settings → Domains → add `whalewatch.uk` and `www.whalewatch.uk`. Vercel will show DNS records to add at your registrar (one A record + one CNAME). Vercel auto-provisions SSL.

After custom domain is live, confirm `MR_CORS_ORIGINS` in the VM's `.env` includes `https://whalewatch.uk` and `https://www.whalewatch.uk` then restart:

```bash
docker compose -f docker/docker-compose.prod.yml up -d backend
```

---

## 9. Smoke test

Open the Vercel URL → `/map`. You should see:
- Macro heatmap when zoomed out (~50,000 res-4 cells from `macro_risk_overview`)
- Detail hexagons when zoomed in (≥ zoom 7)
- Cell click → side panel with sub-score breakdown
- `/classify` → upload a test photo → species predictions
- `/community` → loads (empty until a user submits a sighting)

---

## 10. Operations

**Backups:** weekly DB dump to S3 / Backblaze B2:

```bash
# /etc/cron.weekly/backup_postgres
docker exec marine_risk_postgis_prod \
    pg_dump -U marine -Fc marine_risk \
    > /var/backups/mr_$(date +%F).dump
```

**Updates:**

```bash
cd /opt/marine-risk-mapping
git pull
docker compose -f docker/docker-compose.prod.yml up -d --build backend
```

**Logs:**

```bash
docker compose -f docker/docker-compose.prod.yml logs --tail=200 -f backend
```

**Resource monitoring:** `docker stats` (cheap and good enough for v1).

---

## What's not included yet (v2 backlog)

- Object storage for user uploads (currently a Docker volume — survives restarts but not VM rebuilds)
- CDN in front of `/api/v1/macro/*` and `/api/v1/zones/*` (high read-rate, low cardinality)
- Climate projection marts (42 GB; needs S3 + on-demand load or migration to a managed Postgres with bigger storage)
- Automated CI/CD (GitHub Actions → docker build → push to GHCR → ssh + `docker pull`)
- Sentry / error tracking
- Stronger rate limits + abuse protection (Cloudflare in front would suffice)

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Caddy fails to get cert | DNS not propagated, port 80 blocked | `dig +short api.whalewatch.uk`; check `ufw status` |
| Backend OOM kills | Photo classifier loads 1 GB on first request | Bump VM to 16 GB, or pre-warm by hitting `/api/v1/photo/classify` after deploy |
| `psycopg2.OperationalError` | DB not ready | `docker compose ps` — Postgres healthcheck must pass |
| Frontend shows CORS errors | `MR_CORS_ORIGINS` doesn't include Vercel URL | Add origin to `.env`, restart backend |
| Slow `/api/v1/risk/zones` | Missing index after restore | `REINDEX DATABASE marine_risk;` (one-off, ~5 min) |
