# Security policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately through GitHub's private vulnerability reporting on this repository (Security tab, "Report a vulnerability"). Do not open a public issue for a security problem. Include the affected version or commit, steps to reproduce and the impact you see. Reports are acknowledged as the maintainer is able; this is a solo project and there is no response-time commitment.

## Supported versions

Only the latest commit on `main` is supported.

## What the platform does today

- Production mode refuses to start with a missing, placeholder or short `SECRET_KEY`, and refuses to start if demo accounts exist.
- `seed-demo` refuses to run in production. Demo accounts use reserved `.invalid` addresses and passwords that are new on every run.
- Passwords are hashed with Argon2; administrator passwords must be at least 12 characters.
- Secrets come from environment variables only. The repository holds `.env.example` with placeholders; `.env` files are git-ignored and a secrets scan runs in CI.
- The web server sends a restrictive Content-Security-Policy and standard hardening headers; containers run as non-root, and production containers drop all capabilities.

## Operating guidance

- Put the stack behind TLS (a reverse proxy or the host's load balancer). Keep `WEB_BIND=127.0.0.1` unless you intend to serve a LAN directly.
- Generate `SECRET_KEY` and `POSTGRES_PASSWORD` with at least 32 and 16 random characters and keep them out of version control and slides.
- Create the first administrator from `FIRST_ADMIN_EMAIL` and `FIRST_ADMIN_PASSWORD` or with `make create-admin`; remove the password from the environment afterwards.

A full ASVS level 1 review is planned for wave 14a.
