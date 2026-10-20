# Deploying to an Azure for Students Linux VM

A first-time runbook. It takes you from nothing to the platform running on one Ubuntu virtual machine with HTTPS, backups and a way to update and roll back. Nothing in this repository contacts Azure or holds a credential: you create the VM yourself and everything below runs on it or on your laptop.

**What is verified and what is not.** The deployment scripts and the production stack (including HTTPS through Caddy on a local test domain and a backup and restore round trip) were tested on a laptop with `make prod-check` and `make backup-test`. Anything about Azure itself (portal wording, sizes, regions, prices, credit limits, student restrictions) was written without access to Azure and is marked *unverified*. Check it against what the portal actually shows.

## 1. What you will end up with

```
internet ──443/80──▶ Caddy (automatic HTTPS) ──▶ web (nginx: app + /api proxy) ──▶ api (FastAPI) ──▶ db (Postgres 16)
                                                                                    └─ uploads volume
```

- One VM, one public IP, one DNS name. Caddy is the only thing published to the internet; the database is never published.
- Data lives in Docker volumes on the VM's disk: the database, uploads, and Caddy's certificates.
- Production mode is always on here: the API refuses to start without a strong `SECRET_KEY`, refuses demo accounts, and the first administrator comes only from an environment variable or the `create-admin` command.

## 2. Before you start (on your laptop)

1. `make prod-check` passes (builds the production images and runs the whole production stack, including HTTPS, on a throwaway project).
2. `make backup-test` passes (backup and restore round trip).
3. `docs/HOSTING_OPTIONS.md` has the measured memory of the stack, to help choose the VM size.
4. You have an SSH key pair, or create one now:

   ```sh
   ssh-keygen -t ed25519 -C "azure-vm" -f ~/.ssh/azure_vm
   ```

   `~/.ssh/azure_vm.pub` is the public key you give Azure. Never share the file without `.pub`.

## 3. Azure portal: create the VM

Portal wording and defaults change; the intent of each step matters more than the exact label. *All of this section is unverified against the current portal.*

1. Sign in at the Azure portal with your student account and check that the subscription is **Azure for Students**.
2. **Create a resource → Virtual machine.**
3. **Basics**
   - Resource group: create a new one, for example `trainer-rg`. Deleting this group later removes everything in it.
   - Virtual machine name: for example `trainer-vm`.
   - Region: choose one close to the evaluators. Student subscriptions can restrict regions and sizes; pick from what the portal lets you select.
   - Image: **Ubuntu Server 24.04 LTS - x64 Gen2** (x86_64). Do not choose an Arm image: the instructions and images here are tested for x86_64.
   - Size: pick from the memory figures in `docs/HOSTING_OPTIONS.md`. As a floor, the stack needs a little over 1 GiB of RAM at idle once the host OS is counted; a 4 GiB machine is comfortable. The smallest sizes may run the stack but are too small to build the images on without swap (section 4) or building elsewhere (section 9). Prices: *unverified, check the price shown in the portal*.
   - Authentication type: **SSH public key**. Username: `azureuser`. Paste the contents of `~/.ssh/azure_vm.pub`.
   - Public inbound ports: allow **SSH (22)** for now. You will tighten this in step 6.
4. **Disks:** the OS disk is persistent. A Standard SSD of 30 GiB is a sensible start. Choose "delete with VM" according to whether you want the data to disappear with the VM.
5. **Networking**
   - Create a new public IP and set its assignment to **Static** (a dynamic address can change after you stop the VM, which would break DNS).
   - **Set a DNS name label on the public IP.** Open the VM, then **Overview → Public IP address** (this opens the public IP resource), then **Configuration**. Under **DNS name label (optional)** type a short, unique, lower-case name, for example `trainer-demo`, and **Save**. Azure then gives the VM the name `trainer-demo.<region>.cloudapp.azure.com` (the portal shows the full name on the same page; `<region>` is the region you picked, such as `westeurope`). That is a normal public DNS name, so Caddy can obtain a certificate for it and you do not need a domain of your own. Use exactly this full name as `--domain` in section 6.
6. **Network security group (NSG)** → inbound rules, so that exactly these are open:

   | Port | Source | Why |
   |---|---|---|
   | 22 (SSH) | your own public IP address only | administration |
   | 80 (HTTP) | Any | certificate issuance and redirect to HTTPS |
   | 443 (HTTPS) | Any | the application |

   Add 80 and 443 as new inbound rules; edit the SSH rule to restrict its source to your IP (look it up, and update the rule if your address changes). Do not open 5432 or 8080.
7. **Review + create.** Then note the VM's public IP and DNS name.
8. **Budget alerts (do this now):** **Cost Management + Billing → Cost Management → Budgets → Add.** Create a budget with a small monthly amount and alerts at, say, 50%, 80% and 100% to your email. Student credit is limited and a forgotten VM spends it. *Unverified: how the student credit is shown and what happens when it runs out; check the portal.*
9. **Stopping to save money:** when you are not using the VM, **Stop** it in the portal until the status reads **Stopped (deallocated)**. Shutting down from inside the OS does *not* stop compute billing. Disks (and possibly the static IP) can still cost money while deallocated: *unverified, check the cost analysis*. The containers restart by themselves when the VM starts again (`restart: unless-stopped`), and a static IP keeps the DNS name valid.

## 4. First login and server setup

From your laptop:

```sh
ssh -i ~/.ssh/azure_vm azureuser@<dns-name-or-ip>
```

On the VM, install Docker Engine and the tools the scripts need. These commands follow Docker's published Ubuntu instructions; if Docker has changed them, follow `docs.docker.com/engine/install/ubuntu/` instead.

```sh
sudo apt-get update
sudo apt-get install -y ca-certificates curl git python3
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$USER"
```

Log out and back in so the group change applies, then check:

```sh
docker version
docker compose version
```

Optional hardening: turn on automatic security updates (`sudo apt-get install -y unattended-upgrades`) and disable SSH password login (the VM was created with a key, and Azure disables password login for key-based VMs by default; confirm with `sudo sshd -T | grep passwordauthentication`).

### Add 2 GB of swap before the first build

**Where the images are built:** by default on the VM itself. `infra/deploy.sh up` runs `docker compose up --build`, so the Python dependency install and the web build both run on the VM, and so does every later `update`. Those builds are the memory peak, and a small VM can kill them. Add 2 GB of swap now, before the first deploy (it also protects the running stack):

```sh
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h        # the Swap line should now show 2.0Gi
```

If you would rather not build on the VM at all, build the images for x86_64 on your Mac and load them on the VM instead; see section 9. There is no image registry in this setup, by design: images move with `docker save` and `docker load`.

Docker publishes container ports in a way that bypasses the host firewall (`ufw`). That is fine here because the compose files publish only Caddy's 80 and 443, and the web port on `127.0.0.1`. The NSG from step 6 is your real firewall.

## 5. Get the code onto the VM

The repository is private, so the VM needs read access. Pick one:

- **Deploy key (read-only, recommended).** On the VM: `ssh-keygen -t ed25519 -f ~/.ssh/deploy_key -N ""`, then add `~/.ssh/deploy_key.pub` in GitHub under the repository's **Settings → Deploy keys** (leave "Allow write access" off). Then:

  ```sh
  GIT_SSH_COMMAND="ssh -i ~/.ssh/deploy_key -o IdentitiesOnly=yes" \
    git clone git@github.com:buildwithshikhar/SUDARSHAN.git ~/app
  cd ~/app
  git config core.sshCommand "ssh -i ~/.ssh/deploy_key -o IdentitiesOnly=yes"
  ```

- **Copy from your laptop** (no GitHub access needed on the VM): `rsync -az --exclude .git --exclude node_modules --exclude .env ./ azureuser@<dns>:~/app/`. Updates then mean copying again, and `deploy.sh update` (which uses `git pull`) will not apply.

Never put a token in the repository, in a script, or in a command you paste somewhere shared.

## 6. First deploy

### Before you deploy: check the name and the ports

Caddy gets its certificate from Let's Encrypt by answering a challenge on **port 80** (and it serves on **443**). If either port is blocked, or the name does not point at the VM, no certificate is issued and the site will not open. Check all three from your laptop **before** the first deploy:

1. **The name resolves to the VM's public IP:**

   ```sh
   dig +short trainer-demo.<region>.cloudapp.azure.com     # must print the VM's public IP
   ```

2. **The network security group allows 80 and 443.** In the portal: VM → **Networking** → **Network settings** → **Inbound port rules**. Rules for 80 and 443 must exist with action **Allow**, and nothing with a lower priority number may deny them. Then test reachability. Nothing is listening yet, so the *right* answer is "connection refused", and a timeout means a firewall is dropping the traffic:

   ```sh
   nc -vz -w 5 trainer-demo.<region>.cloudapp.azure.com 80      # refused = reachable (good); timed out = blocked
   nc -vz -w 5 trainer-demo.<region>.cloudapp.azure.com 443
   ```

3. **No firewall on the VM itself is in the way.** On Ubuntu `sudo ufw status` should read `inactive` (or allow 80 and 443); Azure's Ubuntu image ships with it inactive.

Only when all three are right, continue. After the deploy, `infra/deploy.sh check` and `make check-deploy URL=https://<name>` confirm the certificate and the site.

### Deploy

On the VM, in the checkout (`~/app`):

```sh
infra/deploy.sh init --domain trainer-demo.<region>.cloudapp.azure.com --email you@example.com
infra/deploy.sh up
infra/deploy.sh create-admin
infra/deploy.sh check
```

What each does:

- `init` writes `.env` (mode 600, git-ignored) with `APP_ENV=production`, a random `SECRET_KEY`, a random `POSTGRES_PASSWORD`, and your `DOMAIN` and `ACME_EMAIL`. It refuses to overwrite an existing `.env`. Those two environment variables are the only HTTPS configuration. The email is given to the certificate authority for expiry notices.
- `up` builds the images on the VM and starts Postgres, the API, the web server and Caddy. The first build takes several minutes. On a small machine the build can run out of memory; make sure the swap file from section 4 is in place.
- `create-admin` asks for an email and then a password, typed twice and not shown on screen. The password is **never** accepted as a command-line argument (it would appear in the process list and in your shell history), and the command never prints it. The password must be at least 12 characters, not a common one, and not contain the email name.
  - The only other source is the `.env` file: set `FIRST_ADMIN_EMAIL` and `FIRST_ADMIN_PASSWORD` there before `up` and the administrator is created at start. `init` creates `.env` with mode 600 (check with `ls -l .env`; it should read `-rw-------`). Delete the `FIRST_ADMIN_PASSWORD` line afterwards.
  - Nothing else creates accounts in production; demo accounts are refused at start-up and at sign-in.
- `check` runs the deployed-URL checks against `https://<your DOMAIN>`.

Then open `https://<your DOMAIN>` in a browser and sign in with the administrator you created.

If the certificate does not appear: check that ports 80 and 443 are open in the NSG, that the DNS name resolves to the VM's IP (`dig +short <name>` from your laptop), and read `infra/deploy.sh logs caddy`. Certificate authorities rate-limit repeated failures, so fix the cause before restarting in a loop.

## 7. Checking a deployment

From the VM or from your laptop:

```sh
make check-deploy URL=https://<your DOMAIN>
```

This runs, in order: `GET /healthz` (the process is alive, no database needed), `GET /readyz` (the database answers), `GET /api/v1/version` (and that it reports `production`), then a real page load: the HTML shell, its title, and the main script it references. It exits non-zero on the first failure. `make smoke URL=...` runs only the first three. On a VM without `make`, use `infra/check-deploy.sh https://<your DOMAIN>`.

The signed-out end-to-end tests also work against a remote URL: `make e2e URL=https://<your DOMAIN>` (the signed-in tests are skipped because demo accounts do not exist in production).

## 8. Update and roll back

**Update** (on the VM):

```sh
infra/deploy.sh update
```

It refuses to run with uncommitted changes, records the current commit, takes a backup, runs `git pull --ff-only`, rebuilds, restarts, and runs the checks. If the checks fail it tells you how to go back.

**Roll back:**

```sh
infra/deploy.sh rollback
```

It checks out the commit that was deployed before the last update, rebuilds and checks. Database migrations only move forward, so if the failed release changed the schema, also restore the backup that `update` took first (its path is in `.deploy/last-backup`):

```sh
infra/deploy.sh restore <that backup directory>
```

After a rollback the checkout is on a detached commit. Return to normal updates with `git checkout main`.

### Rehearsal: prove update and rollback on the real VM

`deploy.sh update` and `deploy.sh rollback` were written and syntax-checked but have **not** been run against a real server (they need a git remote and a running stack). Run them once, on the VM, before you rely on them, and write the result down. **This verification is open** until the table below has been filled in `docs/BUILD_LOG.md`.

1. Note the current state: `git rev-parse --short HEAD` and `make check-deploy URL=https://<name>` (or `infra/deploy.sh check`).
2. Take a manual backup and check it exists: `infra/backup.sh`, then `ls -l backups/`.
3. **Update.** Push any new commit to `main` from your laptop (a docs-only commit is enough), then on the VM run `infra/deploy.sh update`. Expect: a backup, a pull, a rebuild, `check` passing, and the new commit hash shown. Confirm in the browser that you are still signed in or can sign in.
4. **Roll back.** Run `infra/deploy.sh rollback`. Expect the checkout to return to the previous commit, a rebuild, and `check` passing. Confirm `git rev-parse --short HEAD` equals the hash from step 1.
5. **Return to main.** `git checkout main`, then `infra/deploy.sh update` once more, and check again.
6. **Failure path (optional but valuable).** Temporarily break a build (for example a typo on a throwaway branch on the VM), run `update`, and confirm it stops with the rollback instructions and leaves the previous version running.
7. Record, in `docs/BUILD_LOG.md`: date, VM size, the commits involved, how long the update and rollback took, and anything that did not behave as written here. Fix this runbook for whatever differed.

## 9. Building on a small VM, and building for x86_64 on an ARM Mac

The VM is x86_64. Images built on an Apple-silicon Mac are arm64 and will not run on it, so build where the architecture matches:

- **Build on the VM (default).** `infra/deploy.sh up` does this, so add the swap file first (section 4). `deploy.sh up` also warns when memory plus swap is below 3 GiB.

- **Build on your Mac for x86_64** (the build uses emulation; on the maintainer's M-series laptop `make build-amd64` finished in about 1.5 minutes and produced `amd64` images, but the images were not run on an x86_64 machine):

  ```sh
  make build-amd64            # tags <project>-api:amd64 and <project>-web:amd64
  docker tag sudarshan-api:amd64 sudarshan-api:latest
  docker tag sudarshan-web:amd64 sudarshan-web:latest
  docker save sudarshan-api:latest sudarshan-web:latest | gzip | ssh -i ~/.ssh/azure_vm azureuser@<dns> 'gunzip | docker load'
  ```

  Then on the VM start from the loaded images without building: `NO_BUILD=1 infra/deploy.sh up`. (`sudarshan` is the compose project name, which comes from `brand.json` in lower case.)

## 10. Backups and restore

Data to protect: the database and the uploads volume. Certificates in Caddy's volume are re-issued automatically if lost.

```sh
infra/backup.sh                      # writes backups/<UTC timestamp>/ (db.dump, uploads.tgz, MANIFEST)
infra/deploy.sh restore backups/<timestamp>
```

- `backup.sh` keeps the newest 14 backups (`BACKUP_KEEP`) in `./backups` (`BACKUP_DIR`), with owner-only permissions.
- A backup on the same disk does not protect you if the VM or disk is lost. Copy backups elsewhere regularly, for example from your laptop: `scp -i ~/.ssh/azure_vm -r azureuser@<dns>:~/app/backups ./vm-backups`.
- Nightly backup with cron (`crontab -e` on the VM): `0 2 * * * cd /home/azureuser/app && infra/backup.sh >> /home/azureuser/backup.log 2>&1`.
- `restore` asks you to type `restore`, stops web and api, replaces the database and uploads from the backup, and starts everything again (migrations run on start). It replaces **all** current data.
- Practise a restore somewhere harmless before you need it. `make backup-test` does exactly this round trip on a throwaway stack.

## 11. Adding a domain later

1. Create a DNS `A` record for the domain pointing at the VM's static public IP, and wait for it to resolve.
2. Edit `.env` on the VM: set `DOMAIN=your.domain`.
3. `infra/deploy.sh up` (Caddy obtains a certificate for the new name).

The Azure DNS name stops being served once `DOMAIN` changes. Nothing else changes, because the application uses relative URLs.

## 12. A separately hosted frontend (not the supported path)

A separate frontend host (for example Vercel) is possible in principle: build the web app with `VITE_API_URL=https://api.example` (a build argument in `infra/Dockerfile.web`, or `VITE_API_URL` when running `npm run build`) and set `CORS_ORIGINS=https://frontend.example` on the API. **Be aware** that sign-in uses a `SameSite=Lax` cookie. If the frontend and the API are on different registrable domains, the browser will not send that cookie on cross-site requests, so sign-in would not work without a code change (`SameSite=None; Secure` plus the CSRF protections reviewed for it). That change is not part of wave 2. The supported deployment serves the web app and the API from one origin, as this runbook does.

## 13. Reference

| File | Purpose |
|---|---|
| `infra/docker-compose.yml` | base stack: db, api, web, volumes |
| `infra/docker-compose.prod.yml` | production override: `APP_ENV=production`, required secrets, restart policies, no capabilities |
| `infra/docker-compose.https.yml` and `infra/Caddyfile` | Caddy with automatic HTTPS from `DOMAIN` and `ACME_EMAIL` |
| `infra/deploy.sh` | init, up, update, rollback, check, status, logs, create-admin, backup, restore |
| `infra/backup.sh`, `infra/restore.sh` | data backup and restore |
| `infra/check-deploy.sh`, `infra/smoke.sh` | deployed-URL checks |
| `.env` (not in git) | all secrets and settings; template in `.env.example` |

Environment variables used on the VM:

| Variable | Meaning |
|---|---|
| `APP_ENV` | `production` here |
| `SECRET_KEY` | at least 32 random characters; the API refuses to start otherwise |
| `POSTGRES_PASSWORD` | database password; set when the database volume is first created, so changing it later also needs an `ALTER USER` inside Postgres |
| `DOMAIN`, `ACME_EMAIL` | HTTPS name and certificate contact |
| `FIRST_ADMIN_EMAIL`, `FIRST_ADMIN_PASSWORD` | optional first administrator, created at start; remove the password afterwards |
| `CORS_ORIGINS` | only for a separate frontend (section 12) |
| `WEB_PORT`, `WEB_BIND` | host port and bind address of the web container (default `8080`, `127.0.0.1`) |
| `HTTP_PORT`, `HTTPS_PORT` | Caddy's host ports (default 80 and 443) |
| `BACKUP_DIR`, `BACKUP_KEEP` | where backups go and how many to keep |
| `EVALUATION_MODE`, `VITE_EVALUATION_MODE` | evaluation link only, both `false` by default (section 15) |

## 14. Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `up` stops with "Refusing to start in production: SECRET_KEY…" | `.env` has a missing, placeholder or short `SECRET_KEY`; run `init` on a new checkout or fix the value |
| `up` stops with "demo accounts exist" | the database was created in demo mode; use a clean volume (`docker compose … down -v` removes this project's data) |
| Browser shows a certificate warning | the certificate has not been issued yet; check DNS, ports 80 and 443, and `infra/deploy.sh logs caddy` |
| `check` fails on `/readyz` | the database is not ready or the password changed; `infra/deploy.sh logs db api` |
| Build is killed | out of memory on a small VM; add the swap file (section 4) or build on your Mac (section 9) |
| Cannot SSH after a while | your public IP changed and the NSG rule for port 22 no longer matches it |
| Everyone is locked out of sign-in | too many failed sign-ins from one account or address; the limit clears by itself after 15 minutes |

## 15. Evaluation deployment

**For the public evaluation link only.** Evaluation mode lets evaluators enter any of the four seats (Trainee operator, Detachment commander, Instructor, Administrator) with one click and no password. Do not enable it on any deployment that holds real trainee records, and do not leave it on after the evaluation ends.

**It is off unless both variables are set.**

| Variable | Where it acts | Effect |
|---|---|---|
| `EVALUATION_MODE=true` | API, read at start | Registers `POST /api/v1/auth/evaluation-login` (it returns 404 when the flag is off) and lets a production start keep the seeded seats in the database. Password sign-in to the seats stays refused in production. |
| `VITE_EVALUATION_MODE=true` | Web image, read at **build** time | The sign-in page shows the four seat buttons, each with a one-line description, above "Sign in with an account". Changing it needs an image rebuild (`infra/deploy.sh update` or `up`). |

Both default to `false` in `.env.example`, the compose files and the image build argument. Put the two lines in the git-ignored `.env` on the VM; no credential is involved and none belongs in the repository or the web bundle. The seats use the three seeded accounts (`trainee@`, `instructor@`, `admin@demo.invalid`); the commander seat is a seat of the trainee account. The accounts get a random password at every reset that is never printed or stored anywhere, so they cannot be signed in to with a password at all.

**Set up and reset.**

```
infra/deploy.sh eval-reset        # on the VM; or `make eval-reset` against a local stack
```

Run it once after the first deploy (until it has run, the buttons answer "evaluation seats are not set up") and then daily, ideally from cron at a quiet hour: `0 3 * * *  cd /path/to/repo && infra/deploy.sh eval-reset`. It creates the three seats if missing, resets their language and theme, and deletes their sign-in sessions, training sessions and saved scenarios, so the next visitor finds the seeded state. It never touches other accounts. It exits with an error if `EVALUATION_MODE` is not `true`. Anyone in a live session at that moment is signed out.

**Safety limits.**

- Seeded data only: the seats are the seeded accounts and the seeded screens; nothing in evaluation mode creates real records.
- The entry endpoint counts every request: 20 per 5 minutes per client address, then 429 with `Retry-After`.
- Evaluation sessions last 3 hours (`evaluation_session_ttl_hours` in `app/config.py`), not 12; the cookie is `HttpOnly` and `Secure` in production.
- The Administrator seat cannot reset a password, change a role, deactivate an account, save instance settings or restore a backup: those controls are disabled with the message "Disabled in the evaluation build", and the server refuses an evaluation seat on any route guarded with `forbid_in_evaluation` (to be applied to the user, password, audit and settings routes when they are built). The audit chain can only be verified, not edited.
- No outbound email is configured anywhere, and the screens show no secret.
- Data written during a session (a session record, a saved scenario) is shared by everyone who enters the same seat until the next reset; it is isolated from every real account.

**Checking it.** `make smoke URL=<link>` signs in as each of the four seats and checks the role behind each cookie. Set `EXPECT_EVALUATION=true` to require the entry (the check then fails on a 404), or `EXPECT_EVALUATION=false` to require that it is off. A deployment without the flag must report 404 for `/api/v1/auth/evaluation-login`. See ADR-027.
