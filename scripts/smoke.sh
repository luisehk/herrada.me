#!/usr/bin/env bash
# Container smoke for `make ci` (RK-0029 test T-RK-29-1, HM-0002).
#
# Runs the image on 127.0.0.1, on the first free port from 8650 to 8659, and
# checks what it serves: every site file byte for byte with its type, noindex
# on every page, /health, the missing sheet (404.html) with a 404 for a missing
# path at any depth and for every repo file that must not ship, a 404 and not a
# 403 for a directory with no index (/images/, /fonts/, /assets/: HM-0002
# criterion 4), dot paths denied with a 404,
# the security headers, the cache policy (the page no-cache, assets ten minutes
# on a 200 or a 304, a 404 never cached publicly), no redirect on plain HTTP for
# either host, the nginx master's capability set, the web root holding the site
# files alone, and the image's HEALTHCHECK reaching healthy. The container runs
# with no-new-privileges and every capability dropped but CHOWN, SETGID, SETUID
# and NET_BIND_SERVICE, as the pod runs with allowPrivilegeEscalation off and
# the same capabilities. It is stopped on exit (it runs with --rm, so stopping
# removes it).
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
	if docker run -d --rm --name "$name" --security-opt no-new-privileges \
		--cap-drop ALL --cap-add CHOWN --cap-add SETGID --cap-add SETUID --cap-add NET_BIND_SERVICE \
		-p "127.0.0.1:$p:80" "$image" >/dev/null 2>"$tmp/run.err"; then
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

# The home page, byte for byte, with no redirect on plain HTTP.
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
cc="$(header cache-control)"
if [ "$cc" = no-cache ]; then ok "GET / has Cache-Control: no-cache"; else bad "GET / has Cache-Control '$cc', expected no-cache"; fi

req /style.css
if [ "$code" = 200 ] && cmp -s "$tmp/body" style.css; then ok "GET /style.css -> 200, unchanged"; else bad "GET /style.css -> $code, expected 200 with style.css"; fi
cc="$(header cache-control)"
if [ "$cc" = "public, max-age=600" ]; then ok "GET /style.css has Cache-Control: $cc"; else bad "GET /style.css has Cache-Control '$cc', expected public, max-age=600"; fi
lm="$(header last-modified)"
req /style.css -H "If-Modified-Since: $lm"
cc="$(header cache-control)"
if [ "$code" = 304 ] && [ "$cc" = "public, max-age=600" ]; then ok "a conditional GET /style.css -> 304 with Cache-Control: $cc"; else bad "a conditional GET /style.css -> $code with Cache-Control '$cc', expected 304 with public, max-age=600"; fi

# Every other site file, byte for byte, with its type and its cache policy.
# The pages are no-cache, the files beside them ten minutes.
for f in how-i-build.html 404.html script.js $(git ls-files fonts assets); do
	req "/$f"
	ct="$(header content-type)"
	cc="$(header cache-control)"
	case "$f" in
	*.html) want_ct="text/html"; want_cc="no-cache" ;;
	*.js) want_ct="application/javascript"; want_cc="public, max-age=600" ;;
	*.woff2) want_ct="font/woff2"; want_cc="public, max-age=600" ;;
	*.webp) want_ct="image/webp"; want_cc="public, max-age=600" ;;
	*.txt) want_ct="text/plain"; want_cc="no-cache" ;;
	*) want_ct="?"; want_cc="?" ;;
	esac
	if [ "$code" = 200 ] && cmp -s "$tmp/body" "$f"; then ok "GET /$f -> 200, unchanged"; else bad "GET /$f -> $code, expected 200 with $f"; fi
	if [ "${ct%%;*}" = "$want_ct" ] && [ "$cc" = "$want_cc" ]; then ok "GET /$f is $want_ct with Cache-Control: $cc"; else bad "GET /$f is '$ct' with Cache-Control '$cc', expected $want_ct with $want_cc"; fi
done

# Previews are never indexed: every page carries the robots meta.
for p in / /how-i-build.html /404.html; do
	req "$p"
	if grep -qF '<meta name="robots" content="noindex">' "$tmp/body"; then ok "GET $p carries noindex"; else bad "GET $p has no robots noindex meta"; fi
done

req /health
if [ "$code" = 200 ] && [ "$(tr -d '\n' < "$tmp/body")" = healthy ]; then ok "GET /health -> 200 healthy"; else bad "GET /health -> $code '$(head -c 40 "$tmp/body")', expected 200 healthy"; fi

# A missing path is a 404, never the home page, keeps the security headers and
# shows the missing sheet, at any depth.
for p in /no-such-page /a/b/c.html; do
	req "$p"
	if [ "$code" = 404 ] && cmp -s "$tmp/body" 404.html; then ok "GET $p -> 404 with the missing sheet"; else bad "GET $p -> $code, expected 404 with 404.html"; fi
done
if [ -n "$(header X-Content-Type-Options)" ] && [ -n "$(header X-Frame-Options)" ]; then ok "the 404 keeps the security headers"; else bad "the 404 has no security headers"; fi
cc="$(header cache-control)"
if [ "$cc" = no-cache ]; then ok "the 404 has Cache-Control: no-cache"; else bad "the 404 has Cache-Control '$cc', expected no-cache"; fi

# HM-0002 criterion 4: a directory with no index answers 404, as GitHub Pages
# did, never 403. /images/ is the old site's folder, now gone; /fonts/ and
# /assets/ exist and have no index.
for p in /images/ /fonts/ /assets/; do
	req "$p"
	if [ "$code" = 404 ] && cmp -s "$tmp/body" 404.html; then ok "GET $p -> 404 with the missing sheet"; else bad "GET $p -> $code, expected 404 with 404.html"; fi
done

# A 404 on an asset-like path is never cached publicly.
req /assets/missing.webp
cc="$(header cache-control)"
if [ "$code" = 404 ]; then ok "GET /assets/missing.webp -> 404"; else bad "GET /assets/missing.webp -> $code, expected 404"; fi
if [ -n "$cc" ] && ! printf '%s' "$cc" | grep -qi public; then ok "the asset 404 has Cache-Control: $cc"; else bad "the asset 404 has Cache-Control '$cc', expected one without public"; fi

# Repo files that must not ship.
for p in /CNAME /Makefile /app.mk /docker/Dockerfile /k8s/deployment.yml /docker/nginx.conf /_config.yml /scripts/smoke.sh /50x.html /build/build.py /build/counts.json /images/avatar.webp; do
	req "$p"
	if [ "$code" = 404 ]; then ok "GET $p -> 404"; else bad "GET $p -> $code, expected 404"; fi
done

# Dot paths are denied, and the denial answers as a missing page.
for p in /.git/HEAD /.dockerignore /.gitignore; do
	req "$p"
	if [ "$code" = 404 ] && cmp -s "$tmp/body" 404.html; then ok "GET $p -> 404 (denied)"; else bad "GET $p -> $code, expected 404 with 404.html"; fi
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

# The nginx master runs with the four capabilities alone: CHOWN (bit 0), SETGID
# (6), SETUID (7) and NET_BIND_SERVICE (10) make the bounding set 0x4c1.
capbnd="$(docker exec "$name" awk '/^CapBnd:/ { print $2 }' /proc/1/status 2>/dev/null)"
if [ "$capbnd" = 00000000000004c1 ]; then ok "the nginx master's capability bounding set is CHOWN, SETGID, SETUID and NET_BIND_SERVICE"; else bad "the nginx master's capability bounding set is '$capbnd', expected 00000000000004c1"; fi

# The web root holds the site files and nothing else.
want="$( { printf '%s\n' index.html how-i-build.html 404.html style.css script.js; git ls-files fonts assets; } | sort)"
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
