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

**DNS (Cloudflare or registrar):**
- Add A record: `api.yourdomain.com` → `49.12.34.56`
- Wait for propagation (usually <1 min on Cloudflare).

---

## 3. Server bootstrap

```bash
ssh root@49.12.34.56

# System updates + Docker + git
apt-get update && apt-get -y upgrade
apt-get -y install ca-certificates curl gnupg git ufw
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
    > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Firewall
ufw allow 22
ufw allow 80
ufw allow 443
ufw --force enable

# Clone the repo
cd /opt
git clone https://github.com/Henryhall97/marine-risk-mapping.git
cd marine-risk-mapping
```

---

## 4. Configure environment

```bash
cp .env.prod.example .env
nano .env
```

Fill in:
- `POSTGRES_PASSWORD` — `openssl rand -base64 32`
- `MR_JWT_SECRET` — `openssl rand -hex 32`
- `MR_CORS_ORIGINS` — your Vercel URL(s) (set after frontend deploy)
- `DOMAIN` — e.g. `api.yourdomain.com`

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

## 6. Start Postgres and restore

```bash
# On the VM:
cd /opt/marine-risk-mapping
docker compose -f docker/docker-compose.prod.yml up -d postgis

# Wait for healthy
docker compose -f docker/docker-compose.prod.yml ps

# Restore
docker exec -i marine_risk_postgis_prod \
    pg_restore -U marine -d marine_risk -j 4 --no-owner --no-acl \
    /dumps/marine_risk_prod_*.dump

# Sanity check
docker exec marine_risk_postgis_prod \
    psql -U marine -d marine_risk -c \
    "SELECT count(*) FROM fct_collision_risk;"
# → should print ~1.8M
```

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
curl https://api.yourdomain.com/health
# → {"status":"ok"}
curl 'https://api.yourdomain.com/api/v1/risk/zones?lat_min=40&lat_max=41&lon_min=-71&lon_max=-70&limit=5'
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
   `NEXT_PUBLIC_API_URL` = `https://api.yourdomain.com`
5. Deploy.

After deployment, copy the Vercel URL into the VM's `.env` `MR_CORS_ORIGINS` and restart:

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
| Caddy fails to get cert | DNS not propagated, port 80 blocked | `dig api.yourdomain.com`; check `ufw status` |
| Backend OOM kills | Photo classifier loads 1 GB on first request | Bump VM to 16 GB, or pre-warm by hitting `/api/v1/photo/classify` after deploy |
| `psycopg2.OperationalError` | DB not ready | `docker compose ps` — Postgres healthcheck must pass |
| Frontend shows CORS errors | `MR_CORS_ORIGINS` doesn't include Vercel URL | Add origin to `.env`, restart backend |
| Slow `/api/v1/risk/zones` | Missing index after restore | `REINDEX DATABASE marine_risk;` (one-off, ~5 min) |
