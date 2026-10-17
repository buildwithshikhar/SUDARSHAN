#!/bin/sh
# Guard first (so production never migrates or serves with a bad configuration), then migrate,
# create the first admin if configured, and serve.
set -eu
# The API is reachable only through the web container on the compose network, so forwarded
# client addresses (used by the login rate limit) are trusted.
python -m app.cli check
python -m app.cli migrate
python -m app.cli create-admin --if-configured
exec uvicorn app.main:get_app --factory --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips '*'
