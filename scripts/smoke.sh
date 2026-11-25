#!/usr/bin/env bash
# Container smoke for `make ci` (RK-0029 test T-RK-29-1).
#
# Runs the image on 127.0.0.1, on the first free port from 8650 to 8659, and
# checks what it serves: the three site files byte for byte, /health, a 404 for
# a missing path and for every repo file that must not ship, dot paths denied,
# the security headers, no redirect on plain HTTP for either host, the web root
# holding the site files alone, and the image's HEALTHCHECK reaching healthy.
# The container is stopped on exit (it runs with --rm, so stopping removes it).
#
#   scripts/smoke.sh <image>
set -uo pipefail

image="${1:?usage: scripts/smoke.sh <image>}"
cd "$(dirname "$0")/.." || exit 1

name="herrada-me-smoke-$$"
tmp="$(mktemp -d)"
started=""
cleanup() {
	if [ -n "$started" ]; then docker stop "$name" >/dev/null 2>&1 || true; fi
	rm -rf "$tmp"
}
trap cleanup EXIT

checks=0
failed=0
ok() { checks=$((checks + 1)); echo "ok      $*"; }
bad() { checks=$((checks + 1)); failed=$((failed + 1)); echo "FAILED  $*"; }

# Pick a free port. A port that answers a connect is taken; one docker cannot
# bind is skipped too.
port=""
for p in $(seq 8650 8659); do
	if (exec 3<>"/dev/tcp/127.0.0.1/$p") 2>/dev/null; then continue; fi
	if docker run -d --rm --name "$name" -p "127.0.0.1:$p:80" "$image" >/dev/null 2>"$tmp/run.err"; then
		port="$p"
		started=1
		break
	fi
	docker rm -f "$name" >/dev/null 2>&1 || true
done
if [ -z "$port" ]; then
	echo "FAILED  no free port from 8650 to 8659 for the smoke container: $(head -n 1 "$tmp/run.err" 2>/dev/null)"
	exit 1
fi
base="http://127.0.0.1:$port"
echo "smoke: $image on $base (container $name)"

# Wait for nginx to answer.
for _ in $(seq 1 50); do
	curl -fsS -o /dev/null --max-time 2 "$base/health" 2>/dev/null && break
	sleep 0.2
done

# req <path> [curl args...]: body to $tmp/body, headers to $tmp/headers, the
# status code to $code.
req() {
	local path="$1"
	shift
	code="$(curl -sS -o "$tmp/body" -D "$tmp/headers" -w '%{http_code}' --max-time 5 "$@" "$base$path" 2>/dev/null)" || code="000"
}
header() { grep -i "^$1:" "$tmp/headers" | head -n 1 | cut -d: -f2- | tr -d '\r' | sed 's/^ *//'; }
no_redirect() {
	if grep -qi '^location:' "$tmp/headers"; then bad "$1 sent a redirect: $(header location)"; else ok "$1 sent no redirect"; fi
}

# The page and its two files, byte for byte, with no redirect on plain HTTP.
title="$(sed -n 's:.*<title>\(.*\)</title>.*:\1:p' index.html | head -n 1)"
req /
if [ "$code" = 200 ] && grep -qF "<title>$title</title>" "$tmp/body"; then ok "GET / -> 200 with the title '$title'"; else bad "GET / -> $code, expected 200 with the title '$title'"; fi
if cmp -s "$tmp/body" index.html; then ok "GET / serves index.html unchanged"; else bad "GET / differs from index.html"; fi
no_redirect "GET /"
for h in X-Frame-Options X-Content-Type-Options Referrer-Policy; do
	v="$(header "$h")"
	if [ -n "$v" ]; then ok "GET / has $h: $v"; else bad "GET / has no $h header"; fi
done
if header server | grep -q '[0-9]'; then bad "GET / names the nginx version: $(header server)"; else ok "GET / hides the nginx version"; fi

req /style.css
if [ "$code" = 200 ] && cmp -s "$tmp/body" style.css; then ok "GET /style.css -> 200, unchanged"; else bad "GET /style.css -> $code, expected 200 with style.css"; fi

for f in images/*; do
	req "/$f"
	if [ "$code" = 200 ] && cmp -s "$tmp/body" "$f"; then ok "GET /$f -> 200, unchanged"; else bad "GET /$f -> $code, expected 200 with $f"; fi
done
req /images/avatar.webp
ct="$(header content-type)"
if [ "$code" = 200 ] && [ "$ct" = image/webp ]; then ok "GET /images/avatar.webp is image/webp"; else bad "GET /images/avatar.webp -> $code as '$ct', expected 200 as image/webp"; fi

req /health
if [ "$code" = 200 ] && [ "$(tr -d '\n' < "$tmp/body")" = healthy ]; then ok "GET /health -> 200 healthy"; else bad "GET /health -> $code '$(head -c 40 "$tmp/body")', expected 200 healthy"; fi

# A missing path is a 404, never the home page, and keeps the security headers.
req /no-such-page
if [ "$code" = 404 ]; then ok "GET /no-such-page -> 404"; else bad "GET /no-such-page -> $code, expected 404"; fi
if [ -n "$(header X-Content-Type-Options)" ] && [ -n "$(header X-Frame-Options)" ]; then ok "the 404 keeps the security headers"; else bad "the 404 has no security headers"; fi

# Repo files that must not ship.
for p in /CNAME /Makefile /app.mk /docker/Dockerfile /k8s/deployment.yml /docker/nginx.conf /_config.yml /scripts/smoke.sh /50x.html; do
	req "$p"
	if [ "$code" = 404 ]; then ok "GET $p -> 404"; else bad "GET $p -> $code, expected 404"; fi
done

# Dot paths are denied.
for p in /.git/HEAD /.dockerignore; do
	req "$p"
	if [ "$code" = 403 ]; then ok "GET $p -> 403"; else bad "GET $p -> $code, expected 403"; fi
done

# Plain HTTP as Traefik forwards it from Cloudflare: the origin never redirects,
# on the apex or on www (www's redirect is Traefik's Middleware, not nginx).
for host in herrada.me www.herrada.me; do
	req / -H "Host: $host" -H 'X-Forwarded-Proto: http'
	if [ "$code" = 200 ]; then ok "plain HTTP GET / for $host -> 200"; else bad "plain HTTP GET / for $host -> $code, expected 200"; fi
	no_redirect "plain HTTP GET / for $host"
	req /health -H "Host: $host" -H 'X-Forwarded-Proto: http'
	if [ "$code" = 200 ]; then ok "plain HTTP GET /health for $host -> 200"; else bad "plain HTTP GET /health for $host -> $code, expected 200"; fi
	no_redirect "plain HTTP GET /health for $host"
done

# The web root holds the site files and nothing else.
want="$( { printf '%s\n' index.html style.css; git ls-files images; } | sort)"
got="$(docker exec "$name" find /usr/share/nginx/html -type f 2>/dev/null | sed 's:^/usr/share/nginx/html/::' | sort)"
if [ "$got" = "$want" ]; then ok "the web root holds only: $(echo $want)"; else bad "the web root holds: $(echo $got), expected: $(echo $want)"; fi

# The HEALTHCHECK command works, and Docker reports the container healthy.
if docker exec "$name" wget --no-verbose --tries=1 --spider http://127.0.0.1/health >/dev/null 2>&1; then ok "the HEALTHCHECK command passes in the container"; else bad "the HEALTHCHECK command fails in the container"; fi
health=""
for _ in $(seq 1 45); do
	health="$(docker inspect -f '{{.State.Health.Status}}' "$name" 2>/dev/null)"
	[ "$health" = healthy ] && break
	sleep 1
done
if [ "$health" = healthy ]; then ok "docker reports the container healthy"; else bad "docker reports the container '$health', expected healthy"; fi

echo "smoke: $checks checks, $failed failed"
[ "$failed" -eq 0 ]
