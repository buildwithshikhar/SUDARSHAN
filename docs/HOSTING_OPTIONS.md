# Hosting options for the live link (Q-02)

Prepared offline, without checking any provider's site. **Every price, limit, region, feature and policy below is unverified: check current pricing and terms before choosing.** Nothing here has been deployed or signed up for, and the choice is yours.

## What the platform needs

| Need | Detail |
|---|---|
| Docker Compose | The repo ships `infra/docker-compose.yml` plus a production override: `web` (nginx, unprivileged, port 8080 inside), `api` (uvicorn), `db` (Postgres 16 with a named volume). |
| Database | Postgres 16 in compose today. The API image also supports SQLite through `DATABASE_URL`, but the compose file does not mount a volume for it; a single-container SQLite setup would need a small compose change. |
| Persistent disk | Required for the database, and later for sessions and signed records. Hosts without a persistent disk are out (ADR-006). |
| HTTPS | Required for a public link. The web container speaks plain HTTP and binds `127.0.0.1` by default, so something in front must terminate TLS. |
| Memory | Three small containers; plan for at least 1 GB of RAM for the stack, more once the simulation and WebSocket sessions arrive (wave 3 onward). Unverified, to be measured. |
| CPU architecture | Images build for the machine that builds them. Building on an Apple-silicon laptop gives arm64; most VPS plans are amd64. Build on the host (`docker compose build`) or build multi-arch. |
| Low cost | A free or small monthly tier is enough for evaluators; no scale needed. |
| Simple deploy by you | Ideally `git pull` and one command, with secrets in an `.env` file on the host. Claude Code prepares config and docs and never deploys. |
| Optional | A separately hosted frontend (for example Vercel) needs `VITE_API_URL` at build time and `CORS_ORIGINS` on the API (see CLAUDE.md). The simplest path keeps web and API on one origin. |

## Candidates

### 1. Small VPS running Docker Compose

Examples: Hetzner Cloud, DigitalOcean, Vultr, AWS Lightsail, Linode/Akamai (all unverified as to current plans). A Linux VM you administer.

- **Fit with compose:** native. The repo's compose files run as they are; clone the repo, create `.env`, `docker compose ... up -d --build`.
- **Database and disk:** Postgres in the stack on the VM's disk; add provider snapshots or a nightly `pg_dump` for backups (backup and restore tooling arrives in wave 13c).
- **HTTPS:** add a reverse proxy such as Caddy or Traefik on the host that obtains certificates automatically; needs a domain name pointed at the VM's IP. One extra container or a host package.
- **Cost:** typically the lowest fixed monthly cost for a 1–2 GB machine. Unverified, check current pricing.
- **Deploy by you:** SSH, `git pull`, `docker compose up -d --build`. You own OS updates, firewall and Docker updates.
- **Risks:** you maintain the server; a misconfigured firewall exposes the database port (compose does not publish it, which helps).

### 2. Fly.io with a volume

A container platform that runs Docker images in small VMs with attachable volumes (unverified).

- **Fit with compose:** not compose-native. Each service becomes its own Fly app or process with a `fly.toml`; the repo has none yet, so Claude Code would add per-service config and docs. The web-to-api proxy (`http://api:8000` in `infra/nginx.conf`) would need Fly's private networking name instead.
- **Database and disk:** a volume attaches to one machine in one region (unverified), which suits SQLite on a volume or a Postgres machine. Managed Postgres offerings and their costs change; check current terms. Volume snapshots and retention: unverified.
- **HTTPS:** provided on a `*.fly.dev` hostname, with custom domains supported (unverified).
- **Cost:** pay for running machines and volumes, with a small free allowance that has changed over time. Unverified, check current pricing.
- **Deploy by you:** `fly deploy` from your machine after one-time setup; needs an account and payment method.
- **Risks:** more migration effort than a VPS; a single machine with a single volume is a single point of failure.

### 3. Oracle Cloud Always Free VM

A free-tier VM (Arm or small x86) you administer like a VPS (unverified).

- **Fit with compose:** native, as for a VPS; builds on the host are arm64 on Ampere shapes, which both images support in principle (to be verified by a build there).
- **Database and disk:** block volume attached to the VM; Postgres in the stack.
- **HTTPS:** same as a VPS: a reverse proxy with automatic certificates and a domain.
- **Cost:** advertised as free within limits. Unverified; free-tier eligibility, region capacity and idle-instance reclamation policies are exactly the things to check before relying on it for a demo.
- **Deploy by you:** same as a VPS.
- **Risks:** account approval friction and capacity or reclamation risk right when you need a stable link.

### 4. A machine you already own, with a tunnel

A laptop or mini PC running the compose stack, published through a tunnel service such as Cloudflare Tunnel or similar (unverified), or just served on the LAN.

- **Fit with compose:** native; the same commands as `make demo`, with the production override for a stable run.
- **Database and disk:** local disk and the Docker volume.
- **HTTPS:** supplied by the tunnel service; no open inbound ports.
- **Cost:** no hosting fee; electricity and your machine. Tunnel terms and any account requirement: unverified.
- **Deploy by you:** the simplest, and it matches the product's offline, unit-level LAN use.
- **Risks:** the link is only up when the machine is on and online; evaluators may find it unreachable at the wrong moment. Not suitable as the only link.

## Comparison

| | VPS + Compose | Fly.io | Oracle free VM | Own machine + tunnel |
|---|---|---|---|---|
| Runs repo compose unchanged | Yes | No, per-service config needed | Yes | Yes |
| Persistent disk | Yes | Yes (volume, single machine) | Yes | Yes |
| HTTPS | Add Caddy/Traefik, needs a domain | Built in (unverified) | Add Caddy/Traefik, needs a domain | Via tunnel |
| Cost | Low, fixed (unverified) | Usage-based (unverified) | Free tier (unverified) | None |
| Setup effort for you | Medium | Medium to high | Medium to high | Low |
| Always-on for evaluators | Yes | Yes | Likely (verify policy) | No |
| Extra work for Claude Code | Caddy compose snippet and deploy doc | `fly.toml` per service, proxy change | Same as VPS | Tunnel doc |

## Recommendation

For an evaluator-facing link that must stay up, a small VPS running the repo's compose stack behind Caddy (option 1) fits best: it needs no changes to the existing config, gives a persistent disk, and the deploy is a `git pull` and one command. If you would rather not administer a server, Fly.io is the next choice, at the cost of some extra config work. Keep option 4 as the demo-day fallback, not the primary link.

The decision, and the provider's real pricing, are yours. Once you pick one, note it in `docs/BUILD_LOG.md` (Deployed build, Host) and Claude Code adds the matching `docs/DEPLOY.md` and any proxy config in wave 2. To decide you need: a domain name (or acceptance of a provider subdomain), a payment method if not on a free tier, and a choice of region.
