# OCI Ubuntu VM Deployment Runbook

This runbook deploys the current AUD Generator on a single OCI Compute VM
running Ubuntu. It keeps the current local-first app architecture intact:

- Backend API: FastAPI served by `uvicorn` on `127.0.0.1:8000`
- Worker: `python -m app.workers.local_worker --loop`
- Frontend: Next.js production server on `127.0.0.1:3000`
- Public entry point: Nginx on ports `80` and optionally `443`
- Database: SQLite local-first baseline, or Oracle ADB when configured
- File storage: local filesystem first, stored outside the repository

This plan intentionally does not add Docker, Redis, authentication, or new OCI
service integration. Optional OCI Object Storage, Queue, Speech, Document
Understanding, Generative AI, and Oracle database settings should be enabled
only when those features are required and tested.

## 1. Pick the Access Model

Use one of these two access patterns before opening firewall rules:

- Private/admin-only access: keep only SSH open in OCI and use local SSH tunnels
  to view the app.
- Browser access: put Nginx in front of the app and open only `80` and `443`
  to the required user IP ranges.

For a first deployment, private/admin-only access is safer. You can still see
the full app from your local system with SSH port forwarding.

## 2. Prepare OCI Networking

In the VM's Network Security Group, preferably, or subnet Security List:

- Allow TCP `22` only from your local public IP or office VPN CIDR.
- If using browser access, allow TCP `80` and `443` from the required user CIDR.
- Do not expose backend port `8000` or frontend port `3000` publicly.
- Keep egress open enough for package updates, Git access, and optional OCI SDK
  calls.

On Ubuntu, mirror the same intent with UFW:

```bash
sudo ufw allow from <your-public-ip>/32 to any port 22 proto tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status verbose
```

If you are using SSH tunnels only, skip the `80` and `443` rules.

## 3. Create an App User and Directories

SSH to the VM, then create a dedicated app user and persistent data directory:

```bash
sudo adduser --system --group --home /opt/aud-generator audapp
sudo mkdir -p /opt/aud-generator /var/lib/aud-generator/storage /var/log/aud-generator
sudo chown -R audapp:audapp /opt/aud-generator /var/lib/aud-generator /var/log/aud-generator
```

Store app code in `/opt/aud-generator`. Store runtime data in
`/var/lib/aud-generator` so future code pulls do not touch uploaded files,
generated documents, or the SQLite database.

## 4. Install Runtime Prerequisites

Install the OS tools with your approved Ubuntu package process:

```bash
sudo apt update
sudo apt install -y git curl nginx python3 python3-venv python3-pip
```

Install Node.js 20 LTS or newer using your standard VM image, OS repository, or
approved Node.js package source. Confirm:

```bash
python3 --version
node --version
npm --version
nginx -v
```

## 5. Put the Code on the VM

From the VM, clone or pull the repository into `/opt/aud-generator`. Use your
real repository URL:

```bash
sudo -u audapp git clone <repo-url> /opt/aud-generator
cd /opt/aud-generator
```

Do not copy local `.env`, `.venv`, `node_modules`, `.next`, SQLite files, or
`backend/storage` unless you are intentionally migrating existing data.

## 6. Configure the Backend Environment

Create `/opt/aud-generator/backend/.env` on the VM:

```bash
sudo -u audapp cp /opt/aud-generator/.env.example /opt/aud-generator/backend/.env
sudo -u audapp nano /opt/aud-generator/backend/.env
```

Use one database profile only.

### Option A: SQLite Local-First Baseline

Use this only for the simplest first VM deployment or non-production smoke
testing:

```dotenv
ENVIRONMENT=production
APP_NAME=aud-generator-api

DB_PROVIDER=sqlite
DATABASE_URL=sqlite:////var/lib/aud-generator/aud_generator.db
AUTO_CREATE_TABLES=true

STORAGE_BACKEND=local
LOCAL_STORAGE_ROOT=/var/lib/aud-generator/storage

JOB_QUEUE_BACKEND=local
LOCAL_WORKER_POLL_INTERVAL_SECONDS=5

DEFAULT_AUD_TEMPLATE_PATH=/opt/aud-generator/backend/template/AUD_Editable_Template.docx
MAX_SPREADSHEET_ROWS_PER_SHEET=200
INTERNAL_DEBUG_OUTPUT=false
EMAIL_NOTIFICATIONS_ENABLED=true
EMAIL_NOTIFICATION_URL=https://apex.oraclecorp.com/pls/apex/basic_learning_01/apka/send-email
EMAIL_NOTIFICATION_FROM=audacle@oracle.com
EMAIL_NOTIFICATION_DOWNLOAD_BASE_URL=https://<vm-public-ip-or-domain>/api
EMAIL_NOTIFICATION_TIMEOUT_SECONDS=10
EMAIL_NOTIFICATION_VERIFY_SSL=true
EMAIL_NOTIFICATION_TRUST_ENV=true
EMAIL_NOTIFICATION_CA_BUNDLE=

LLM_PROVIDER=none
DOCUMENT_AI_PROVIDER=none

BACKEND_CORS_ORIGINS=["http://<vm-public-ip-or-domain>"]
```

### Option B: Oracle Autonomous Database

Use this when the VM should run against Oracle ADB:

```dotenv
ENVIRONMENT=production
APP_NAME=aud-generator-api

DB_PROVIDER=oracle
DATABASE_URL=
AUTO_CREATE_TABLES=false

ORACLE_DB_USER=<database-user>
ORACLE_DB_PASSWORD=<database-password>
ORACLE_DB_DSN=<tns-alias-or-connect-descriptor>
ORACLE_DB_WALLET_DIR=/opt/aud-generator-secrets/adb-wallet
ORACLE_DB_WALLET_PASSWORD=<optional-wallet-password>
ORACLE_DB_ECHO=false
ORACLE_DB_POOL_SIZE=5
ORACLE_DB_MAX_OVERFLOW=10
ORACLE_DB_POOL_PRE_PING=true

STORAGE_BACKEND=local
LOCAL_STORAGE_ROOT=/var/lib/aud-generator/storage

JOB_QUEUE_BACKEND=local
LOCAL_WORKER_POLL_INTERVAL_SECONDS=5

DEFAULT_AUD_TEMPLATE_PATH=/opt/aud-generator/backend/template/AUD_Editable_Template.docx
MAX_SPREADSHEET_ROWS_PER_SHEET=200
INTERNAL_DEBUG_OUTPUT=false
EMAIL_NOTIFICATIONS_ENABLED=true
EMAIL_NOTIFICATION_URL=https://apex.oraclecorp.com/pls/apex/basic_learning_01/apka/send-email
EMAIL_NOTIFICATION_FROM=audacle@oracle.com
EMAIL_NOTIFICATION_DOWNLOAD_BASE_URL=https://<vm-public-ip-or-domain>/api
EMAIL_NOTIFICATION_TIMEOUT_SECONDS=10
EMAIL_NOTIFICATION_VERIFY_SSL=true
EMAIL_NOTIFICATION_TRUST_ENV=true
EMAIL_NOTIFICATION_CA_BUNDLE=

LLM_PROVIDER=none
DOCUMENT_AI_PROVIDER=none

BACKEND_CORS_ORIGINS=["http://<vm-public-ip-or-domain>"]
```

Keep ADB wallet files outside the Git checkout and make them readable only by
the `audapp` user:

```bash
sudo mkdir -p /opt/aud-generator-secrets/adb-wallet
sudo chown -R audapp:audapp /opt/aud-generator-secrets
sudo chmod -R go-rwx /opt/aud-generator-secrets
```

With `DB_PROVIDER=oracle`, keep `DATABASE_URL` blank unless you intentionally
want to override all provider-specific database settings with a full SQLAlchemy
URL. When `DATABASE_URL` is non-empty, the application uses it directly.

If Nginx serves HTTPS, use `https://<domain>` in `BACKEND_CORS_ORIGINS`. If you
only use SSH tunnels and local testing, keep `http://127.0.0.1:3000` and
`http://localhost:3000` in that JSON array.

## 7. Configure the Frontend Environment

Create `/opt/aud-generator/frontend/.env.production`:

```bash
sudo -u audapp nano /opt/aud-generator/frontend/.env.production
```

For Nginx path-based routing, use:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://<vm-public-ip-or-domain>/api
```

For HTTPS:

```dotenv
NEXT_PUBLIC_API_BASE_URL=https://<domain>/api
```

For SSH tunnel-only access during the first smoke test:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:18000
```

Rebuild the frontend every time `NEXT_PUBLIC_API_BASE_URL` changes because
public Next.js environment variables are compiled into the browser bundle.

## 8. Install App Dependencies and Build

Backend:

```bash
cd /opt/aud-generator/backend
sudo -u audapp python3 -m venv .venv
sudo -u audapp .venv/bin/python -m pip install --upgrade pip
sudo -u audapp .venv/bin/python -m pip install -r requirements.txt
```

Frontend:

```bash
cd /opt/aud-generator/frontend
sudo -u audapp npm ci
sudo -u audapp npm run build
```

Run a backend smoke check before creating services:

```bash
cd /opt/aud-generator/backend
sudo -u audapp .venv/bin/python -m pytest tests/test_health.py tests/test_config.py tests/test_database_url.py
```

## 9. Create Systemd Services

Create `/etc/systemd/system/aud-backend.service`:

```ini
[Unit]
Description=AUD Generator FastAPI backend
After=network.target

[Service]
Type=simple
User=audapp
Group=audapp
WorkingDirectory=/opt/aud-generator/backend
ExecStart=/opt/aud-generator/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/aud-worker.service`:

```ini
[Unit]
Description=AUD Generator local job worker
After=network.target aud-backend.service
Requires=aud-backend.service

[Service]
Type=simple
User=audapp
Group=audapp
WorkingDirectory=/opt/aud-generator/backend
ExecStart=/opt/aud-generator/backend/.venv/bin/python -m app.workers.local_worker --loop
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/aud-frontend.service`:

```ini
[Unit]
Description=AUD Generator Next.js frontend
After=network.target aud-backend.service

[Service]
Type=simple
User=audapp
Group=audapp
WorkingDirectory=/opt/aud-generator/frontend
Environment=NODE_ENV=production
ExecStart=/usr/bin/npm run start -- -H 127.0.0.1 -p 3000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

If `npm` is not at `/usr/bin/npm`, update `ExecStart` with the path from
`which npm`.

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now aud-backend aud-worker aud-frontend
sudo systemctl status aud-backend aud-worker aud-frontend --no-pager
```

## 10. Configure Nginx

Create `/etc/nginx/sites-available/aud-generator`:

```nginx
server {
    listen 80;
    server_name <vm-public-ip-or-domain>;

    client_max_body_size 200m;

    location = /api {
        return 308 /api/;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 1800;
        proxy_send_timeout 1800;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable it:

```bash
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/aud-generator /etc/nginx/sites-enabled/aud-generator
sudo nginx -t
sudo systemctl reload nginx
```

Add TLS with your approved certificate process. After TLS is enabled, update
`frontend/.env.production` and `backend/.env`, rebuild the frontend, and restart
the services.

## 11. Verify From the VM

Run:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/db
curl http://127.0.0.1:3000
curl -H "Host: <vm-public-ip-or-domain>" http://127.0.0.1/api/health
```

Expected results:

- `/health` returns `{"status":"ok","service":"aud-generator-api"}`.
- `/health/db` returns `status=ok`, `can_connect=true`, and SQLite dialect.
- Frontend HTML is returned from port `3000`.
- Nginx path `/api/health` reaches the backend.

## 12. Monitor From Your Local System

SSH status snapshot:

```bash
ssh ubuntu@<vm-public-ip> "systemctl --no-pager --full status aud-backend aud-worker aud-frontend nginx"
```

Follow logs:

```bash
ssh ubuntu@<vm-public-ip> "journalctl -u aud-backend -n 100 -f"
ssh ubuntu@<vm-public-ip> "journalctl -u aud-worker -n 100 -f"
ssh ubuntu@<vm-public-ip> "journalctl -u aud-frontend -n 100 -f"
ssh ubuntu@<vm-public-ip> "sudo tail -f /var/log/nginx/error.log"
```

Open local tunnels without exposing app ports publicly:

```bash
ssh -L 18000:127.0.0.1:8000 -L 13000:127.0.0.1:3000 ubuntu@<vm-public-ip>
```

Then open:

```text
http://127.0.0.1:13000
http://127.0.0.1:18000/health
http://127.0.0.1:18000/health/db
```

Useful VM checks:

```bash
ssh ubuntu@<vm-public-ip> "df -h / /var/lib/aud-generator"
ssh ubuntu@<vm-public-ip> "du -sh /var/lib/aud-generator/storage"
ssh ubuntu@<vm-public-ip> "free -h"
ssh ubuntu@<vm-public-ip> "ss -ltnp | grep -E ':(80|443|3000|8000)'"
```

In OCI, enable Compute Instance Monitoring through Oracle Cloud Agent when
available and create alarms for high CPU, low disk space, memory pressure, and
instance reachability.

## 13. Make Future Changes Safely

Use this update flow:

```bash
ssh ubuntu@<vm-public-ip>
cd /opt/aud-generator
sudo -u audapp git fetch origin
sudo -u audapp git status --short
sudo -u audapp git pull --ff-only

cd backend
sudo -u audapp .venv/bin/python -m pip install -r requirements.txt
sudo -u audapp .venv/bin/python -m pytest tests/test_health.py tests/test_config.py tests/test_database_url.py

cd ../frontend
sudo -u audapp npm ci
sudo -u audapp npm run build

sudo systemctl restart aud-backend aud-worker aud-frontend
curl http://127.0.0.1:8000/health/db
curl -H "Host: <vm-public-ip-or-domain>" http://127.0.0.1/api/health
```

Before changes that touch models, storage, or AUD generation, take a backup:

```bash
sudo systemctl stop aud-worker aud-backend
sudo tar -C /var/lib -czf /var/backups/aud-generator-$(date +%F-%H%M).tgz aud-generator
sudo systemctl start aud-backend aud-worker
```

For SQLite deployments, remember that startup `create_all()` creates missing
tables but does not alter existing tables for every schema change. For Oracle
ADB, keep `AUTO_CREATE_TABLES=false` and apply Alembic migrations as part of the
release process after backing up or snapshotting the database.

## 14. Manual End-to-End Smoke Test

From your browser:

1. Open the frontend URL.
2. Create a project.
3. Upload a small supported DOCX or TXT file.
4. Click Generate AUD or run a smaller developer job.
5. Watch `aud-worker` logs until the job reaches a terminal state.
6. Refresh the project page and confirm jobs, extracted content, and generated
   document panels update as expected.
7. Download a generated DOCX when available.

Expected result: the API remains healthy, the worker processes queued jobs, the
frontend can call the `/api` backend route, and files are written under
`/var/lib/aud-generator/storage`.

## References

- OCI Network Security Groups: https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/networksecuritygroups.htm
- OCI Security Lists: https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/securitylists.htm
- OCI Monitoring overview: https://docs.oracle.com/en-us/iaas/Content/Monitoring/Concepts/monitoringoverview.htm
- OCI Monitoring alarms: https://docs.oracle.com/en-us/iaas/Content/Monitoring/Tasks/managingalarms.htm
