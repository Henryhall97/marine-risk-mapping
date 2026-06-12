# Deployment Guide — Marine Risk Mapping

> **Battle-tested runbook.** Reflects the lessons from the v1 deployment to Hetzner + Vercel. Follow top-to-bottom for a clean rebuild on a fresh VM / fresh domain.

```
                     User browser
                         │
                         ▼
            ┌────────────────────────┐
            │ Vercel (Next.js, edge) │   whalewatch.uk
            └────────────┬───────────┘   www.whalewatch.uk
                         │ HTTPS, /static/* rewrites
                         ▼
            ┌────────────────────────┐
            │ Caddy 2  (auto-HTTPS)  │   api.whalewatch.uk
            └────────────┬───────────┘
                ┌────────┴────────┐
                ▼                 ▼
    ┌────────────────────┐  ┌────────────────────┐
    │ FastAPI (uvicorn)  │  │ /static  → bind     │
    │ + ML classifiers   │  │   frontend/public  │
    └─────────┬──────────┘  └────────────────────┘
              │
              ▼
    ┌────────────────────┐
    │ PostGIS 16-3.4     │  /opt/marine-risk-mapping/db_dumps mounted RO
    │ ~ 60 GB on disk    │
    └────────────────────┘
```

Single VM hosts Postgres + Backend + Caddy via Docker Compose. Vercel hosts the frontend and rewrites large static asset paths back to the VM so we don't bundle copyrighted models / large photos in git.

---

## 0. Prerequisites

On your **laptop**:
- Local stack running (`cd docker && docker compose up -d`) so `pg_dump` can run inside `marine_risk_postgis`.
- DB seeded via `dbt build` + ingestion / aggregation jobs.
- ML classifier artefacts in `data/processed/ml/{photo_classifier,audio_classifier}`.
- SSH key pair (`~/.ssh/id_ed25519`).
- ~50 GB free disk for dumps.

On a **registrar** (we used GoDaddy):
- A domain you control (we use `whalewatch.uk`).

---

## 1. Provision the VM — Hetzner

Recommended size for the climate-projection-included build (60+ GB on-disk DB, occasional 58M-row aggregates):

| Spec | Choice | €/mo |
|---|---|---|
| **Type** | CCX23 (or CPX31 if budget-tight) | €30 / €15 |
| vCPU / RAM | 4 / 16 GB (or 4 / 8 GB) | |
| Disk | 160 GB SSD (must be ≥ 100 GB) | |
| Image | Ubuntu 24.04 LTS | |
| Location | Helsinki / Falkenstein / Ashburn | |

Smallest tested working: **ubuntu-16gb-hel1-2** (CCX23). 8 GB will work but the backend image build will be tight.

1. Hetzner Cloud → **Add Server** → choose options above.
2. Paste your `~/.ssh/id_ed25519.pub` under SSH keys.
3. Note the public IPv4 (e.g. `135.181.108.104`).

---

## 2. DNS

Point an `api.<your-domain>` A record at the VM. Apex + www go to Vercel.

At the registrar (GoDaddy → DNS):

| Type | Name | Value | Notes |
|---|---|---|---|
| A | `api` | `<VM_IP>` | The VM's IP |
| A | `@` | `76.76.21.21` | Vercel anycast — apex domain |
| CNAME | `www` | `cname.vercel-dns.com` | Vercel www subdomain |

⚠️ **GoDaddy gotcha:** disable "Domain Forwarding" on the apex record before adding the `@` A record, or it will silently override your A record and serve a parking page. Domain Settings → Forwarding → cancel any forward.

Verify propagation:
```bash
dig +short api.whalewatch.uk    # → <VM_IP>
dig +short whalewatch.uk        # → 76.76.21.21
dig +short www.whalewatch.uk    # → CNAME chain ending at Vercel
```

---

## 3. Bootstrap the VM

One command installs Docker + ufw + clones the repo:

```bash
ssh root@<VM_IP>
curl -fsSL https://raw.githubusercontent.com/Henryhall97/marine-risk-mapping/main/scripts/bootstrap_vm.sh | bash
```

When it finishes you're in `/opt/marine-risk-mapping` with Docker installed and ports 22 / 80 / 443 open in ufw.

---

## 4. Configure environment

Compose looks for `.env` next to the **compose file**, not at repo root. Two equivalent fixes — use a symlink (cleaner) or always pass `--env-file`:

```bash
cd /opt/marine-risk-mapping
cp .env.prod.example .env
ln -s ../.env docker/.env     # so plain `docker compose` finds it
```

Edit `.env`:

```bash
nano .env
```

Required values (avoid `$`, `` ` ``, `\` in passwords — they break compose interpolation):

```env
POSTGRES_DB=marine_risk
POSTGRES_USER=marine
POSTGRES_PASSWORD=<openssl rand -base64 32 | tr -d '/+=' | cut -c1-32>
MR_JWT_SECRET=<openssl rand -hex 32>
DOMAIN=api.whalewatch.uk
MR_CORS_ORIGINS=https://whalewatch.uk,https://www.whalewatch.uk,https://marine-risk-mapping.vercel.app
```

Notes:
- `POSTGRES_PASSWORD` is read **only on the first** `docker compose up postgis` (when the cluster is initialised). Changing it later requires `ALTER USER`.
- `POSTGRES_USER` and `POSTGRES_DB` **must match the dump** (`marine` / `marine_risk`).
- `MR_JWT_SECRET` change invalidates all existing logins — fine on day one, painful later.

---

## 5. Dump the database (on laptop)

```bash
# Core API tables (~3 GB compressed, ~10 GB on disk after restore)
./scripts/dump_prod_db.sh

# Climate projection tables (~8 GB compressed, ~50 GB on disk after restore)
./scripts/dump_projections.sh
```

Both scripts write to `db_dumps/marine_risk_*_<date>.dump`.

The split exists because the projections are large (58M-row tables × 4) and not strictly required for v1. Skip step 5b/7c below if you're tight on VM disk.

---

## 6. Upload assets to the VM (laptop)

Run from project root:

```bash
# 1. Database dumps (~30-60 min for ~12 GB on home broadband)
scp -C db_dumps/marine_risk_prod_*.dump \
    root@<VM_IP>:/opt/marine-risk-mapping/db_dumps/

scp -C db_dumps/marine_risk_projections_*.dump \
    root@<VM_IP>:/opt/marine-risk-mapping/db_dumps/

# 2. Static assets + ML models + user uploads (~610 MB)
scripts/upload_assets.sh root@<VM_IP>
```

`upload_assets.sh` rsyncs six directories:

| Source (local) | Destination (VM) | Served via |
|---|---|---|
| `frontend/public/models/` | `…/frontend/public/models/` | Caddy `/static/models/*` |
| `frontend/public/species/` | `…/frontend/public/species/` | Caddy `/static/species/*` |
| `frontend/public/wizard/` | `…/frontend/public/wizard/` | Caddy `/static/wizard/*` |
| `data/processed/ml/photo_classifier/` | `…/data/processed/ml/photo_classifier/` | Bind-mount into `backend` container |
| `data/processed/ml/audio_classifier/` | `…/data/processed/ml/audio_classifier/` | Bind-mount into `backend` container |
| `data/uploads/` | `…/data/uploads/` | Bind-mount; served by `/api/v1/media/*` |

Why this dance? Whale GLBs are copyrighted (Sketchfab licence) and species photos / wizard images are large — neither belong in git. The frontend's `next.config.ts` rewrites `/models/*`, `/species/*`, `/wizard/*` to `${NEXT_PUBLIC_API_URL}/static/*` in production, so component code is unchanged.

⚠️ **macOS rsync gotcha:** the system rsync is 2.6.9 and doesn't support `--info=progress2`. The script uses `--progress` instead. For a nicer single-line bar, `brew install rsync`.

---

## 7. Start Postgres and restore the DB (on VM)

```bash
cd /opt/marine-risk-mapping
docker compose --env-file .env -f docker/docker-compose.prod.yml up -d postgis

# Wait for healthy
docker compose --env-file .env -f docker/docker-compose.prod.yml ps postgis
```

### 7a. Verify dump is visible inside the container

```bash
docker exec marine_risk_postgis_prod ls -lh /dumps/
# Should list both .dump files
```

⚠️ If empty: the bind-mount path is `../db_dumps:/dumps:ro` (relative to `docker/`). Confirm `db_dumps/` is at the **repo root**, not inside `docker/`.

### 7b. Restore main dump (~5–10 min)

```bash
bash scripts/restore_prod_db.sh
```

Sanity check at end should show roughly:

```
fct_collision_risk          | 1816708
fct_collision_risk_seasonal | 7266832
fct_collision_risk_ml       | 7266832
macro_risk_overview         |  670107
species_crosswalk           |     138
```

If `species_crosswalk` shows **0** — dbt seeds were excluded from the dump. Either rerun `dbt seed` against the prod DB, or `\copy` the CSV in manually.

### 7c. Restore projections (optional, ~30–60 min)

```bash
docker exec marine_risk_postgis_prod \
    pg_restore -U marine -d marine_risk \
    --jobs=4 --no-owner --no-acl \
    /dumps/marine_risk_projections_*.dump
```

⚠️ **Critical: `ANALYZE` the new tables** before querying. Without statistics, the 58M-row aggregate queries plan terribly and hang for minutes:

```bash
docker exec marine_risk_postgis_prod psql -U marine -d marine_risk -c "
ANALYZE fct_collision_risk_ml_projected;
ANALYZE whale_sdm_projections;
ANALYZE whale_isdm_projections;
ANALYZE int_ocean_covariates_projected;
"
```

Verify row counts:
```bash
docker exec marine_risk_postgis_prod psql -U marine -d marine_risk -c "
SELECT relname, n_live_tup FROM pg_stat_user_tables
WHERE relname LIKE '%projected%' OR relname LIKE '%projection%'
ORDER BY relname;"
```

Targets: ~58.1M / 58.1M / 58.1M / 61.7M.

---

## 8. Build and start backend + Caddy (on VM)

First build downloads ~700 MB of torch wheels — expect **5–10 min**:

```bash
docker compose --env-file .env -f docker/docker-compose.prod.yml up -d --build

docker compose --env-file .env -f docker/docker-compose.prod.yml logs -f backend caddy
```

Wait for:
- `Application startup complete` from `marine_risk_backend`
- `certificate obtained successfully` from `marine_risk_caddy` (~30 s after first hit on the domain)

`Ctrl-C` out of logs, then:
```bash
docker compose --env-file .env -f docker/docker-compose.prod.yml ps
# All three containers should be Up / healthy
```

---

## 9. Smoke test (from laptop)

```bash
# 1. Backend health
curl https://api.whalewatch.uk/health
# → {"status":"ok"}

# 2. Static asset served by Caddy
curl -I https://api.whalewatch.uk/static/models/blue_whale.glb
# → HTTP/2 200, content-type: model/gltf-binary

# 3. Risk zones (small bbox)
curl 'https://api.whalewatch.uk/api/v1/risk/zones?lat_min=41.5&lat_max=42.5&lon_min=-71&lon_max=-70&limit=3'

# 4. Macro overview
curl 'https://api.whalewatch.uk/api/v1/macro/overview?season=annual' | head -c 300

# 5. Climate projections (only if step 7c done)
curl 'https://api.whalewatch.uk/api/v1/layers/sdm-projections/summary?lat_min=40&lat_max=42&lon_min=-71&lon_max=-69&species=blue_whale'

# 6. Media (uploaded sighting photo)
docker exec marine_risk_backend ls /app/data/uploads/submissions/ | head -3
```

---

## 10. Deploy frontend to Vercel

1. Vercel UI → **Import** → `Henryhall97/marine-risk-mapping`.
2. **Framework preset:** Next.js
3. **Root directory:** `frontend`
4. **Environment variable:** `NEXT_PUBLIC_API_URL` = `https://api.whalewatch.uk`
5. Deploy.
6. **Custom domains:** Project Settings → Domains → add `whalewatch.uk` (Primary) and `www.whalewatch.uk`. Vercel issues SSL automatically once DNS resolves.

After domains are live, confirm `MR_CORS_ORIGINS` in the VM's `.env` includes the apex and www, then restart the backend:

```bash
docker compose --env-file .env -f docker/docker-compose.prod.yml restart backend
```

---

## 11. Browser smoke test

Open `https://whalewatch.uk` → `/map`:
- Heatmap renders when zoomed out (macro res-4 grid)
- Hex detail when zoomed in (≥ zoom 7)
- Click a hex → side panel with sub-scores
- Logo + nav icons render (committed to git)
- Whale silhouettes render in `/community`, `/verify`, landing page (committed to git)
- 3D whales swim on landing page (Caddy `/static/models/`)
- Species cards on `/species` show photos (Caddy `/static/species/`)
- ID wizard on `/report` shows guides (Caddy `/static/wizard/`)
- `/classify` upload returns a prediction (ML bind-mount)

---

## 12. Day-2 ops

**Pull a code update:**
```bash
ssh root@<VM_IP>
cd /opt/marine-risk-mapping
git pull
docker compose --env-file .env -f docker/docker-compose.prod.yml up -d --build backend
```

**Re-sync assets after editing locally:**
```bash
# Laptop
scripts/upload_assets.sh root@<VM_IP>
```

**Tail logs:**
```bash
docker compose --env-file .env -f docker/docker-compose.prod.yml logs --tail=200 -f backend
```

**Backups (cron weekly):**
```bash
# /etc/cron.weekly/backup_postgres
docker exec marine_risk_postgis_prod \
    pg_dump -U marine -Fc marine_risk > /var/backups/mr_$(date +%F).dump
```

**Resource check:** `docker stats` (good enough for v1).

---

## 13. Migrating to a new VM

Re-do steps 1 → 4 → 7 → 8 → 9 with one tweak: dump from the **current** VM rather than your laptop:

```bash
# On old VM
docker exec marine_risk_postgis_prod pg_dump \
    -U marine -d marine_risk -Fc -Z 9 \
    -f /tmp/migrate_$(date +%F).dump
docker cp marine_risk_postgis_prod:/tmp/migrate_$(date +%F).dump \
    /opt/marine-risk-mapping/db_dumps/

# Pull from old to laptop, then push to new VM
scp -C root@<OLD_IP>:/opt/marine-risk-mapping/db_dumps/migrate_*.dump db_dumps/
scp -C db_dumps/migrate_*.dump root@<NEW_IP>:/opt/marine-risk-mapping/db_dumps/

# Don't forget to re-sync assets + uploads
scripts/upload_assets.sh root@<NEW_IP>
```

Update DNS A record (`api`) to the new IP. Caddy will provision a fresh cert on first request to the new IP.

---

## 14. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `WARN ... POSTGRES_PASSWORD is not set` | Compose can't find `.env` | `ln -s ../.env docker/.env` or always pass `--env-file .env` |
| `pg_restore: could not open input file "/dumps/..."` | Dump not under `db_dumps/` at repo root | Move dump there; mount path is `../db_dumps` (relative to `docker/`) |
| Caddy stuck "obtaining certificate" | Port 80 blocked or DNS not propagated | `ufw status`; `dig +short api.whalewatch.uk` |
| `psycopg2.OperationalError` on backend | DB password mismatch (already-init'd cluster) | Match `.env` to existing password OR `docker volume rm <project>_postgis_data` and re-restore |
| 404 on `/static/...` | Caddy can't see mounted dir | `docker exec marine_risk_caddy ls /srv/static/models/` should not be empty |
| 500 on `/api/v1/...` referencing a table | Table missing | Check `pg_stat_user_tables`; rerun relevant restore |
| Climate projection endpoint hangs | No statistics on freshly restored tables | Run `ANALYZE` on the four projection tables (see 7c) |
| Logo / silhouettes 404 | Forgot to git-commit them | `.gitignore` has explicit `!` exceptions for `whale_watch_logo.png`, `southern_right_wale.jpg`, `whale_detailed_smooth_icons/` |
| `whalewatch.uk` shows GoDaddy parking | Apex A record still default | Set `@` A → `76.76.21.21`; cancel domain forwarding |
| Frontend CORS errors | `MR_CORS_ORIGINS` missing the host | Edit `.env`, restart backend |
| `rsync: unrecognized option --info=progress2` | macOS system rsync 2.6.9 | Script now uses `--progress`; or `brew install rsync` |
| Slow `/api/v1/risk/zones` after restore | Indexes warm-up | One-off `REINDEX DATABASE marine_risk;` (~5 min) |
| Pre-commit blocks file > 500 KB | Logo etc. exceeds limit | One-shot `git commit --no-verify` (do this rarely and intentionally) |

---

## 15. Cost (v1)

| Service | Spec | $/mo |
|---|---|---|
| Hetzner CCX23 | 4 vCPU / 16 GB / 160 GB | ~€30 (~$33) |
| Vercel Hobby | Frontend | $0 |
| Domain | `.uk` annual ÷ 12 | ~$1 |
| **Total** | | **~$34/mo** |

DigitalOcean equivalent ≈ $84/mo, AWS RDS+ECS ≈ $200/mo. Hetzner is the sweet spot for v1.

---

## 16. v2 backlog

- Object storage (S3 / R2) for user uploads — currently a host bind-mount, doesn't survive VM rebuilds without rsync.
- CDN in front of `/api/v1/macro/*` and `/api/v1/zones/*` (high-read, low-cardinality).
- GitHub Actions CI/CD: build → push to GHCR → ssh + `docker pull`.
- Sentry / error tracking + uptime monitoring.
- Cloudflare in front for DDoS / rate-limit / cache.
- Materialised summary table for coast-wide projection summaries (avoid 58M-row sequential scans).
- Hot-standby Postgres replica + offsite backups (currently snapshot-only via Hetzner).
