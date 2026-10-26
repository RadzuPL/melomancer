#!/usr/bin/env bash
# Starts the built image and checks that it really works before it is pushed:
# health endpoint, first-run administrator login, tools inside the image, file ownership.
# Usage: scripts/smoke_test.sh <image>
set -euo pipefail

image="${1:-melomancer:ci}"
name="melomancer-smoke"
port=18080
base="http://127.0.0.1:${port}"
jar="$(mktemp)"

docker rm -f "$name" >/dev/null 2>&1 || true
docker run -d --name "$name" -p "${port}:8080" \
  -e ADMIN_PASSWORD='smoke-test-password-1' -e PUID=1000 -e PGID=1000 "$image" >/dev/null

cleanup() {
  echo "--- container log (tail) ---"
  docker logs "$name" 2>&1 | tail -30 || true
  docker rm -f "$name" >/dev/null 2>&1 || true
  rm -f "$jar"
}
trap cleanup EXIT

ok=0
for _ in $(seq 1 40); do
  if curl -fsS "${base}/api/health" >/dev/null 2>&1; then ok=1; break; fi
  sleep 1
done
[ "$ok" = 1 ] || { echo "FAIL: /api/health never answered"; exit 1; }
echo "health: $(curl -fsS "${base}/api/health")"

curl -fsS -c "$jar" -H 'X-Melomancer: 1' -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"smoke-test-password-1"}' "${base}/api/auth/login" >/dev/null
echo "login ok, system: $(curl -fsS -b "$jar" "${base}/api/system")"
curl -fsS "${base}/" | grep -q "Melomancer" || { echo "FAIL: index page missing"; exit 1; }
curl -fsSI "${base}/static/app.js" | head -n1

docker exec "$name" ffmpeg -version | head -n1
docker exec "$name" ffprobe -version | head -n1
docker exec "$name" deno --version | head -n1
docker exec "$name" python -c "import yt_dlp, discord, davey; print('yt-dlp', yt_dlp.version.__version__, '| discord.py', discord.__version__)"

owner="$(docker exec "$name" stat -c %u:%g /data/melomancer.db)"
[ "$owner" = "1000:1000" ] || { echo "FAIL: /data/melomancer.db is owned by $owner, expected 1000:1000"; exit 1; }
echo "data ownership: $owner"
echo "smoke test passed"
