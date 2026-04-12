# InfraForge v1

Infrastructure lab platform. Two separated planes: the product SaaS, and the lab execution runtime.

---

## Honest state of this codebase

### What works right now

| Component | Status | Notes |
|-----------|--------|-------|
| Platform API (FastAPI) | Ready | Auth, labs, runs, portfolio, scoring routers all written |
| Database schema | Ready | Alembic migration creates all 11 tables |
| Celery workers | Ready | Scoring, badge awards, stale-run sweep, stats refresh |
| Lab orchestrator | Ready | Docker SDK provisioning, network isolation, credential injection |
| Grading engine | Ready | 3-layer scoring, shell/http/process/file check types |
| Lab sweeper | Ready | Kills orphaned containers and networks |
| Next.js frontend | Ready | Dashboard, catalog, run page, portfolio pages |
| Nginx config | Ready | TLS, rate limiting, security headers |
| Observability | Ready | Prometheus, Grafana, Loki, Alertmanager rules |
| 5 lab templates | Ready | YAML scenario + grading spec for each |
| Docker Compose | Ready | Full local stack wired up |

### What does NOT exist yet

These are real blockers. The platform will start; the lab runtime will not fully work without them.

**1. Lab Docker images — not built**
The templates reference these images:
```
infraforge/lab-linux-service-outage:v1
infraforge/lab-docker-compose-debug:v1
infraforge/lab-aws-iam-repair:v1
infraforge/lab-k8s-recovery:v1
infraforge/lab-terraform-broken:v1
```
None of these images exist. Each needs a `Dockerfile` that sets up the broken starting state (systemd, broken configs, LocalStack, k3s, etc.). This is a significant build effort — probably 1–2 days per lab image to do properly.

**What this means:** The orchestrator service will start fine. When a user clicks "Launch lab," the provision call will fail with `docker pull` errors because the image doesn't exist.

**2. Seed data — no fixture loader**
The `labs` table in PostgreSQL is empty on first boot. No labs are visible to users until an admin creates them via the API and marks them `is_published=true`. There is no seed script.

**3. Stripe billing — stub only**
The Stripe secret key is wired in config and the `subscriptions` table exists, but there is no webhook handler, no checkout session creation, and no subscription upgrade/downgrade logic. The paywall check works (free vs. pro tier enforcement is in the runs router), but you cannot actually charge anyone.

**4. Lab VM path — not built**
`FEATURE_VM_LABS=false` in `.env.example` for a reason. No libvirt/cloud API integration exists.

**5. Admin backoffice — no UI**
There is an `is_admin` guard and a `POST /api/v1/labs` endpoint. That's it. Lab creation, version publishing, and user management must be done by hitting the API directly with a curl/httpie command from an admin account.

**6. TLS certificates — not included**
`infra/nginx/certs/` is gitignored. Nginx will refuse to start without `fullchain.pem` and `privkey.pem` in that directory.

**7. One Celery bug**
`update_lab_stats` task in `app/workers/tasks.py` has a SQLAlchemy dialect bug in the `pass_rate` average cast. It will throw on first run. The other three tasks (scoring, badge awards, stale-run sweep) are fine.

---

## How to launch

### Prerequisites

- Docker Engine 24+ with Compose plugin
- A Linux host (the orchestrator mounts `/var/run/docker.sock`)
- 8GB RAM minimum for the full stack; 4GB if you skip observability

### Step 1 — Environment

```bash
cd infraforge
cp .env.example .env
```

Open `.env` and set every value. Do not leave any as `change_me_*`. The minimum required:

```
POSTGRES_PASSWORD=...      # any strong password
REDIS_PASSWORD=...
SECRET_KEY=...             # python -c "import secrets; print(secrets.token_hex(32))"
ORCHESTRATOR_API_KEY=...   # python -c "import secrets; print(secrets.token_hex(32))"
GRADER_API_KEY=...         # python -c "import secrets; print(secrets.token_hex(32))"
MINIO_ROOT_USER=infraforge
MINIO_ROOT_PASSWORD=...
GRAFANA_PASSWORD=...
```

Stripe and SMTP keys are optional until you need billing and email.

### Step 2 — TLS (for local dev, self-signed is fine)

```bash
mkdir -p infra/nginx/certs
openssl req -x509 -newkey rsa:4096 -keyout infra/nginx/certs/privkey.pem \
  -out infra/nginx/certs/fullchain.pem -days 365 -nodes \
  -subj "/CN=localhost"
```

For production: use Certbot / Let's Encrypt and point the cert paths here.

### Step 3 — Start the data plane first

```bash
docker compose up -d postgres redis minio

# Wait for postgres to be healthy (takes ~10s)
docker compose ps postgres   # State should be "healthy"
```

### Step 4 — Start the platform

```bash
docker compose up -d platform-api platform-worker platform-scheduler
```

The `platform-api` container runs `alembic upgrade head` before starting uvicorn.
Watch the logs to confirm migrations complete:

```bash
docker compose logs -f platform-api
# You should see: "INFO  [alembic.runtime.migration] Running upgrade -> 001, Initial schema"
# Then: "Application startup complete."
```

### Step 5 — Start the frontend and edge

```bash
docker compose up -d platform-frontend nginx
```

### Step 6 — Observability (optional but recommended)

```bash
docker compose up -d prometheus grafana loki promtail
```

### Step 7 — Lab runtime (PARTIAL — lab images don't exist yet)

```bash
docker compose up -d lab-orchestrator lab-grader lab-sweeper registry
```

These containers will start. The orchestrator and grader APIs will be reachable.
But no lab can be provisioned until the lab images are built (see below).

### Step 8 — Seed the first lab

The API is up but the labs table is empty. Create an admin user and seed the first lab:

```bash
# Register (first user — you'll manually set their role to admin in postgres)
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@infraforge.io","username":"admin","password":"yourpassword","display_name":"Admin"}' | jq

# Promote to admin directly in postgres
docker compose exec postgres psql -U infraforge -d infraforge \
  -c "UPDATE users SET role='admin' WHERE username='admin';"

# Login to get a token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@infraforge.io","password":"yourpassword"}' | jq -r .access_token)

# Create a lab
curl -s -X POST http://localhost:8000/api/v1/labs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "slug": "linux-service-outage",
    "title": "Linux Service Outage Triage",
    "description": "A webapp service has crashed and disk is at 97%. Diagnose and restore.",
    "category": "linux",
    "difficulty": "intermediate",
    "estimated_minutes": 25,
    "is_free": true
  }' | jq
```

---

## How users access the platform

### Local development

| Service | URL | Notes |
|---------|-----|-------|
| Platform (via nginx) | https://localhost | Accept the self-signed cert warning |
| Platform API (direct) | http://localhost:8000 | Bypasses nginx, no TLS |
| API docs (Swagger) | http://localhost:8000/api/docs | Only in non-production |
| Grafana | http://localhost:3001 | admin / your GRAFANA_PASSWORD |
| Prometheus | http://localhost:9090 | Unauthenticated in dev |
| MinIO console | http://localhost:9001 | MINIO_ROOT_USER / MINIO_ROOT_PASSWORD |

The frontend is at `https://localhost`. Users register, get a JWT, browse labs, launch a run.
While a run is active, the run page shows SSH credentials. They SSH in, do the work, submit.

### Production

1. **DNS** — point `infraforge.io` (or your domain) at your server's IP.
2. **TLS** — replace the self-signed cert with a Let's Encrypt cert in `infra/nginx/certs/`.
3. **Update nginx.conf** — change `server_name infraforge.io www.infraforge.io;` to your domain.
4. **Port 80/443** — must be open on the server firewall.
5. **Separate lab workers** — the orchestrator binds `/var/run/docker.sock`. In production you want the lab runtime on a dedicated node (or nodes), not the same machine as the API. The `docker-compose.yml` works for a single-node setup; multi-node requires Nomad or Kubernetes for the lab runtime plane.

The SSH port range (20000–29999) must also be open in the firewall for users to reach their lab environments. Each active lab run maps one port in that range on the orchestrator host.

### The user flow end to end

```
User registers / logs in
        ↓
Browses lab catalog → clicks a lab → reads scenario
        ↓
Clicks "Launch lab"
        ↓
platform-api creates ChallengeRun row (status: provisioning)
        ↓
Background task → OrchestratorClient.provision_lab()
        ↓
lab-orchestrator → Docker SDK:
  - creates isolated bridge network (if-run-<id>-net)
  - pulls lab image
  - runs container with resource limits, cap_drop, injected SSH password
  - maps SSH port on host
        ↓
Credentials returned → stored in challenge_runs.access_credentials
Run status → "running"
        ↓
Frontend polls /api/v1/runs/<id> every 3s
Displays SSH host:port + password when status=running
        ↓
User opens terminal:
  ssh user@<host> -p <port>
  Password: <shown on screen>
        ↓
User works in the broken environment
        ↓
User clicks "Submit for grading" (or timeout fires)
        ↓
platform-api → Celery → OrchestratorClient.trigger_grading()
        ↓
lab-orchestrator → lab-grader:
  - runs all checks from grading_spec (shell, http, process, file)
  - scores each layer (correctness / safety / efficiency)
  - returns structured result
        ↓
Celery task stores ScoringResult + ScoreBreakdown rows
Creates PortfolioItem with shareable slug
        ↓
lab-orchestrator → Docker: tears down container + network
        ↓
Frontend shows score breakdown, summary, link to portfolio
User shares:  https://infraforge.io/portfolio/p/<slug>
```

---

## Building the lab images (the real next step)

Each lab image needs a `Dockerfile` that:
1. Starts from a base (Ubuntu 22.04, or `python:3.11-slim`, etc.)
2. Installs the required software
3. Copies and runs `setup.sh` at container start to create the broken state
4. Runs an SSH daemon so users can connect

Minimal structure:

```dockerfile
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y openssh-server systemd nginx python3 \
    && rm -rf /var/lib/apt/lists/*

COPY setup.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 22

CMD ["/docker-entrypoint.sh"]
```

The `entrypoint.sh` should:
1. Set the SSH password from `$LAB_SSH_PASSWORD` env var
2. Start `sshd`
3. Run the lab-specific `setup.sh` to introduce the break
4. Block (tail -f /dev/null or similar)

Build and push to the local registry:

```bash
docker build -t localhost:5000/lab-linux-service-outage:v1 \
  -f lab-runtime/templates/linux-service-outage/Dockerfile \
  lab-runtime/templates/linux-service-outage/

docker push localhost:5000/lab-linux-service-outage:v1
```

Then update the `image_tag` in `lab_versions` to point to `localhost:5000/lab-linux-service-outage:v1`.
