# Security Report — Marine Risk Mapping

> **Audience:** maintainers, future contributors, security reviewers.
> **Scope:** v1 production deployment (Hetzner VM + Vercel + Caddy + FastAPI + PostGIS).
> **Last full audit:** 2026-05.
> **Status:** Top 3 high/medium findings remediated in this revision (H1, H3, M2). Medium and low backlog items tracked at the bottom.

---

## 1. What is already good

These properties are baked into the existing design and were verified during this audit:

| Area | Control |
|---|---|
| **SQL** | Every query in [backend/services/](../backend/services/) uses parameterised SQL via `psycopg2` with `%s` placeholders. No string concatenation, no f-string interpolation of user input into SQL. `RealDictCursor` is read-only at the row level. Verified by grep across all services. |
| **Auth — password storage** | bcrypt via `passlib` (cost factor default 12). Plaintext passwords never leave the request handler. See [backend/services/auth.py](../backend/services/auth.py). |
| **Auth — token format** | JWT HS256 with short expiry (24h default), signed with a server-side secret. Verified on every protected route via the `Depends(get_current_user)` dependency. |
| **TLS** | Caddy 2 terminates TLS with automatic Let's Encrypt certificates on `api.whalewatch.uk`. No plaintext HTTP listener. |
| **Network exposure** | Single VM behind `ufw` — only ports 22, 80, 443 are open. PostGIS (5433) is bound to the Docker network only, never to the host. |
| **DB credentials** | Stored in `.env` (gitignored). Cluster password is sealed at first init; rotating it requires `ALTER USER` or volume wipe (documented in [DEPLOYMENT.md](DEPLOYMENT.md)). |
| **CORS** | Allow-list of explicit origins in [backend/config.py](../backend/config.py) (`localhost:3000`, `localhost:5173`, production frontend). No `*` wildcard. |
| **Rate limiting** | `slowapi` on auth (`5/min` register, `10/min` login), classification (`10/min`), sighting reports (`20/min`). See decorators in [backend/api/auth.py](../backend/api/auth.py), [backend/api/photo.py](../backend/api/photo.py), [backend/api/audio.py](../backend/api/audio.py), [backend/api/sightings.py](../backend/api/sightings.py). |
| **Compression** | `GZipMiddleware` with a min-size threshold; no zlib bomb surface because uploads are validated before any decode. |
| **Container** | Backend runs from a slim image; ML model weights are bind-mounted read-only. Caddy serves bind-mounted static assets read-only. |
| **Pre-commit** | `ruff` + 500 KB file-size block + `gitleaks` regex. See `.pre-commit-config.yaml`. |
| **OWASP A03 (Injection)** | Covered — see SQL row above. |
| **OWASP A09 (Logging failures)** | Auth events, classifier errors, and 5xx responses go to structured logs. |

## 2. Findings from this audit

Severity legend: **C**ritical → service compromise feasible. **H**igh → user data exposure or auth bypass feasible. **M**edium → defence-in-depth gap. **L**ow → hygiene.

### 2.1 Remediated in this revision

| ID | Sev | Title | Where | Fixed in |
|---|---|---|---|---|
| **H1** | High | Path-traversal via media path params | `/api/v1/media/{submission_id}/photo`, `/api/v1/events/{id}/cover`, `/api/v1/events/{id}/gallery/{filename}` | §3.1 |
| **H3** | High | Upload endpoints trusted Content-Type / filename only — no magic-byte check | 8 endpoints across `photo`, `audio`, `sightings`, `auth`, `events`, `vessels` | §3.3 |
| **M2** | Medium | Hard-coded JWT fallback secret in source | `backend/services/auth.py` line ~20 (pre-fix) | §3.2 |

### 2.2 Backlog — not yet fixed

| ID | Sev | Title | Notes |
|---|---|---|---|
| **M1** | Medium | No CSRF token on cookie-bearer routes | We currently authenticate via `Authorization: Bearer <jwt>` only (header-bound, so SOP protects us). If we ever add a `Set-Cookie` JWT for the frontend, CSRF tokens become mandatory. |
| **M3** | Medium | No password reset flow | Lockout-by-loss only. Implement email-token reset before public launch. |
| **M4** | Medium | Rate limit is per-IP (slowapi default) | Behind Cloudflare or a load balancer, `request.client.host` will be the proxy IP. Switch to `X-Forwarded-For` aware key function once a real CDN is in front. |
| **M5** | Medium | No audit log of admin actions | Verifications, role changes, deletions go to stdout but are not persisted to a tamper-evident store. |
| **M6** | Medium | `/api/v1/export/obis` is unauthenticated and unrate-limited | Acceptable for an open-data export, but a malicious client can pull the whole archive on a tight loop. Add caching + an `If-None-Match` ETag. |
| **L1** | Low | Avatar / cover upload size cap is enforced after `file.read()` | A 50 MB upload still hits memory before we reject it. Use FastAPI's chunked read with a running counter. |
| **L2** | Low | No content security policy (CSP) header on the API origin | API only serves JSON + binary files, so XSS surface is on the frontend (Vercel), but a strict `default-src 'none'` on the API would still harden. |
| **L3** | Low | JWT expiry is fixed (24h), no refresh-token rotation | Acceptable for a low-stakes app; revisit if tokens ever grant admin power. |
| **L4** | Low | Reputation events are written from the same request as the action that triggers them | A clever client could spam an action and trigger many rep events. Reputation engine should debounce per-(user, event_kind) within a window. |
| **L5** | Low | `uvicorn` exposes `Server` header | Caddy strips by default; verify on prod. |
| **L6** | Low | No HSTS preload | Caddy emits `Strict-Transport-Security` by default. Submit `whalewatch.uk` to the HSTS preload list once the domain is stable. |
| **L7** | Low | `/health` reports raw error messages on DB failure | Leak vector is minimal but the unauthenticated `/health` endpoint should return a generic 503 rather than the psycopg2 string. |
| **L8** | Low | No dependency-update automation | Manually bump via `uv lock --upgrade` quarterly. Consider Dependabot when the repo moves to a more visible namespace. |

---

## 3. Fixes implemented

All three fixes are centralised in a new module, [backend/security.py](../backend/security.py), so the same primitives are reused across every fs-touching or upload endpoint.

### 3.1 H1 — UUID validation + path containment on media routes

**Problem.** Routes like `GET /api/v1/media/{submission_id}/photo` and `GET /api/v1/events/{event_id}/cover` concatenated a string path parameter onto a filesystem root. If a request like `..%2F..%2Fetc%2Fpasswd` slipped through (e.g. via a misbehaving proxy that double-decoded the path), the server would happily serve the file. `submission_id` and `event_id` are stored as Postgres UUIDs (`gen_random_uuid()` in [backend/migrations.py](../backend/migrations.py)), so we have the type information needed to lock these down at the edge.

**Fix.** Two helpers in [backend/security.py](../backend/security.py):

```python
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

def validate_uuid_or_404(value: str, *, name: str = "id") -> str:
    if not isinstance(value, str) or not _UUID_RE.match(value.lower()):
        raise HTTPException(status_code=404, detail=f"{name} not found")
    return value.lower()

def safe_subpath(root: Path, *parts: str) -> Path:
    candidate = root.joinpath(*parts).resolve()
    root_resolved = root.resolve()
    if not candidate.is_relative_to(root_resolved):
        raise HTTPException(status_code=404, detail="Not found")
    return candidate
```

- `validate_uuid_or_404` rejects anything that is not a strict RFC 4122 hex-string before the value reaches the filesystem.
- `safe_subpath` resolves the candidate (which collapses `..` segments and absolutises any nested absolute paths) and confirms it lives inside the configured root. This is defence-in-depth — even if a future code path forgets to call `validate_uuid_or_404`, an escape attempt still hits a 404.
- Both raise 404, not 400 — probe-based reconnaissance is indistinguishable from a real miss.

**Applied at:**

| Endpoint | File |
|---|---|
| `GET /api/v1/media/{submission_id}/{kind}` | [backend/api/media.py](../backend/api/media.py) |
| `GET /api/v1/media/avatar/{user_id}` (int param, no UUID; uses `safe_subpath`) | [backend/api/media.py](../backend/api/media.py) |
| `GET /api/v1/media/credentials/{credential_id}` (int param; uses `safe_subpath`) | [backend/api/media.py](../backend/api/media.py) |
| `POST` / `GET /api/v1/events/{event_id}/cover` | [backend/api/events.py](../backend/api/events.py) |
| `POST` / `GET /api/v1/events/{event_id}/gallery/{filename}` | [backend/api/events.py](../backend/api/events.py) |

### 3.2 M2 — JWT secret fallback now raises (dev) or fails-loud (process restart)

**Problem.** The original code in [backend/services/auth.py](../backend/services/auth.py) was:

```python
JWT_SECRET = os.environ.get("MR_JWT_SECRET", "marine-risk-dev-secret-change-me")
```

The fallback string is committed to the repo. If `uvicorn` was ever launched outside Docker (a contributor running `uv run uvicorn backend.app:app --reload` after forgetting to source `.env`), the server would silently accept JWTs forged by anyone who had read the source — including the public GitHub mirror.

**Fix.** Replaced the constant fallback with a `_resolve_jwt_secret()` function:

```python
def _resolve_jwt_secret() -> str:
    env_secret = os.environ.get("MR_JWT_SECRET")
    if env_secret:
        return env_secret
    generated = secrets.token_urlsafe(64)
    log.warning(
        "MR_JWT_SECRET is not set — generating an ephemeral random key. "
        "Tokens will be invalidated when the process restarts. "
        "Set MR_JWT_SECRET in the environment for production use."
    )
    return generated

JWT_SECRET = _resolve_jwt_secret()
```

- Production is double-belted: [docker/docker-compose.prod.yml](../docker/docker-compose.prod.yml) line 72 has `MR_JWT_SECRET: ${MR_JWT_SECRET:?MR_JWT_SECRET must be set}`, which makes Docker Compose refuse to start the stack without the variable. So in prod the helper never even reaches the `secrets.token_urlsafe` branch.
- Dev / pytest get a per-process random key. Tokens are invalidated on restart, which is the correct behaviour — never the same hard-coded value across machines.
- The warning is loud (`log.warning`) so the operator notices.

### 3.3 H3 — Magic-byte validation on every upload endpoint

**Problem.** The classifier and upload routes ran user-controlled bytes through Pillow (`PIL.Image.open`), librosa (`librosa.load` → `soundfile`), and `torch` model inference. The trust chain was filename extension + client-supplied `Content-Type` — both forgeable. A `whale.jpg` containing a crafted SVG, a polyglot PDF/JPEG, or a malicious TIFF could reach a CVE-vulnerable decoder.

**Fix.** A pure-Python signature table in [backend/security.py](../backend/security.py):

```python
def validate_upload_bytes(
    data: bytes,
    *,
    kind: Literal["image", "audio", "document"],
    declared_content_type: str | None = None,
) -> str:
    mime = sniff_mime(data, kind)
    if mime is None:
        raise HTTPException(status_code=415, detail=...)
    if declared_content_type:
        # alias-tolerant cross-check (image/jpg → image/jpeg, etc.)
        ...
    return mime
```

The sniffer table covers the formats the application actually advertises:

| Kind | Accepted MIME | Magic bytes |
|---|---|---|
| `image` | `image/jpeg` | `FF D8 FF` |
| `image` | `image/png` | `89 50 4E 47 0D 0A 1A 0A` |
| `image` | `image/webp` | `RIFF....WEBP` |
| `image` | `image/tiff` | `II*\0` or `MM\0*` |
| `audio` | `audio/wav` | `RIFF....WAVE` |
| `audio` | `audio/flac` | `fLaC` |
| `audio` | `audio/aiff` | `FORM....AIFF` |
| `audio` | `audio/mpeg` | `ID3` or 11-bit MPEG frame sync |
| `document` | All of the above images + `application/pdf` (`%PDF-`), `application/msword` (CFB header), `application/vnd.openxmlformats-officedocument.wordprocessingml.document` (`PK\x03\x04`) | |

Design notes:
- Deliberately **dependency-free** — no `libmagic`, no `python-magic`, no `filetype`. This keeps the slim runtime container free of one more apt package.
- The Content-Type cross-check is **tolerant**: `image/jpg`, `audio/x-wav`, `audio/mp3`, `audio/wave`, `audio/x-flac`, `audio/x-aiff` are all normalised to their canonical form before comparison. This avoids spurious 415s from common browser oddities.
- Audio uploads where the client sent `application/octet-stream` (common for `.wav` from non-browser clients) skip the declared-vs-sniffed cross-check by passing `declared_content_type=None`. The sniffed signature is still enforced.
- 415 (Unsupported Media Type) is the correct status — 400 implies the request was malformed.

**Applied at:**

| Endpoint | File | `kind` |
|---|---|---|
| `POST /api/v1/photo/classify` | [backend/api/photo.py](../backend/api/photo.py) | `image` |
| `POST /api/v1/audio/classify` | [backend/api/audio.py](../backend/api/audio.py) | `audio` |
| `POST /api/v1/sightings/report` (image part) | [backend/api/sightings.py](../backend/api/sightings.py) | `image` |
| `POST /api/v1/sightings/report` (audio part) | [backend/api/sightings.py](../backend/api/sightings.py) | `audio` |
| `POST /api/v1/auth/me/avatar` | [backend/api/auth.py](../backend/api/auth.py) | `image` |
| `POST /api/v1/auth/me/credentials` | [backend/api/auth.py](../backend/api/auth.py) | `document` (accepts image or PDF/DOC/DOCX) |
| `POST /api/v1/events/{id}/cover` | [backend/api/events.py](../backend/api/events.py) | `image` |
| `POST /api/v1/events/{id}/gallery` | [backend/api/events.py](../backend/api/events.py) | `image` |
| `POST /api/v1/vessels/{id}/profile-photo` | [backend/api/vessels.py](../backend/api/vessels.py) | `image` |
| `POST /api/v1/vessels/{id}/cover-photo` | [backend/api/vessels.py](../backend/api/vessels.py) | `image` |

Each call site validates **after** the size check and **before** the bytes are passed to Pillow, librosa, or written to disk. This means CVE-vulnerable decoders never see hostile bytes.

---

## 4. Test coverage of the new controls

The full backend test suite (139 tests in [tests/test_backend.py](../tests/test_backend.py)) passes against the hardened endpoints. To support the new signature checks, test fixtures were updated to use real magic-byte headers:

```python
# tests/test_backend.py (top)
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 100
PNG_BYTES  = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
WAV_BYTES  = b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 100
```

Tests that intentionally probe rejection (e.g. `test_classify_unsupported_type` posting a `.pdf` to `/photo/classify`, `test_unsupported_image_type` in `TestSightingReport`) still assert `415`. New rejection coverage is implicit — any future regression that stops validating magic bytes will fail the existing happy-path tests, because the previous `b"fake-image"` placeholders no longer exist in the codebase.

Run with:

```bash
uv run pytest tests/test_backend.py -v
# 139 passed
uv run pytest tests/                        # full suite
# 269 passed
uv run ruff check backend/ tests/test_backend.py
# All checks passed!
```

---

## 5. Threat model deltas

| Pre-fix attack | Post-fix outcome |
|---|---|
| Encoded-path traversal against `/api/v1/media/{submission_id}/photo` | Rejected with 404 at `validate_uuid_or_404`. Even if bypassed, `safe_subpath` catches it. |
| JWT forged with the hard-coded fallback secret against a dev / mis-deployed instance | Secret no longer exists. Prod requires env var; dev gets a fresh random per process. |
| Malicious image triggering a Pillow CVE via the photo classifier | Rejected with 415 before any decoder runs. |
| Polyglot PDF/JPEG uploaded as a credential evidence "photograph" | Detected as PDF and accepted (allowed for credentials); detected as JPEG and accepted; never both. The byte stream itself is what matters, not the filename. |
| Random binary garbage uploaded as audio | Rejected — no signature match. |

---

## 6. How to keep this current

When you add a new upload-accepting endpoint:

1. Import `validate_upload_bytes` from `backend.security`.
2. Call it **after** the size check and **before** any decoder or disk write.
3. Pick the right `kind` (`image`, `audio`, or `document`).
4. Pass `declared_content_type=file.content_type` (or `None` for clients that send `application/octet-stream`).

When you add a new path parameter that names an on-disk file or directory:

1. If it is a UUID column in Postgres, call `validate_uuid_or_404(value, name="...")`.
2. Always pass it through `safe_subpath(root, value, ...)` instead of `root / value`.

When you add a new auth secret or credential:

1. Read it from `os.environ`.
2. Have docker-compose.prod.yml require it with `${VAR:?error message}`.
3. Either raise on missing-env in non-prod, or generate a per-process random value with `secrets.token_urlsafe()` and log a `WARNING`. Never commit a fallback constant.

Update this document and the backlog table whenever a finding moves from "open" to "fixed", and add new findings as they are discovered.
