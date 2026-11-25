#!/usr/bin/env bash
# Static checks for `make ci` (RK-0029). Nothing here talks to a cluster.
#
#   1. GitHub Pages publishes the site alone, until Pages goes off on
#      2026-12-02. Jekyll skips paths with a part that starts with '.' or '_'
#      and the names _config.yml excludes; every other tracked file publishes,
#      and each must be CNAME, one of the three pages (index.html,
#      how-i-build.html, 404.html), style.css, script.js or a file under fonts/
#      or assets/ (HM-0002). The build in build/ stays out.
#   2. k8s/deployment.yml has no leading document marker (Jekyll would read it
#      as front matter), keeps the one image line `make cd` pins, and names
#      the herrada-me namespace alone. The pod keeps its hardening: no
#      ServiceAccount token, the RuntimeDefault seccomp profile, no privilege
#      escalation and every capability dropped (the four nginx needs are added
#      back by name).
#   3. app.mk deploys from master: no origin/main is left from vim-puzzles. Its
#      copy_pull_secret creates the Secret and never applies it (rentaventa-k8s
#      ADR 0005: Secrets applied only if absent).
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

checks=0
failed=0
ok() { checks=$((checks + 1)); echo "ok      $*"; }
bad() { checks=$((checks + 1)); failed=$((failed + 1)); echo "FAILED  $*"; }

# 1. What Pages would publish.
excludes="$(sed -n '/^exclude:/,/^[^ ]/s/^  - \(.*\)$/\1/p' _config.yml)"
if [ -n "$excludes" ]; then ok "_config.yml excludes: $(echo $excludes)"; else bad "_config.yml has no exclude list"; fi
published=""
while IFS= read -r f; do
	case "/$f" in */.* | */_*) continue ;; esac
	top="${f%%/*}"
	skip=""
	for e in $excludes; do
		if [ "$top" = "$e" ] || [ "$f" = "$e" ]; then skip=1; fi
	done
	[ -n "$skip" ] && continue
	published="$published $f"
	case "$f" in
	CNAME | index.html | how-i-build.html | 404.html | style.css | script.js | fonts/* | assets/*) ;;
	*) bad "GitHub Pages would publish $f; add it to _config.yml's exclude list" ;;
	esac
done < <(git ls-files)
for f in CNAME index.html how-i-build.html 404.html style.css script.js; do
	case " $published " in *" $f "*) ;; *) bad "GitHub Pages would not publish $f" ;; esac
done
ok "GitHub Pages publishes:$published"

# 2. The manifest.
m=k8s/deployment.yml
if [ "$(head -n 1 "$m")" = "---" ]; then bad "$m opens with a document marker"; else ok "$m opens without a document marker"; fi
n="$(grep -cE '^[[:space:]]*image: ghcr\.io/luisehk/herrada-me:latest$' "$m")"
if [ "$n" = 1 ]; then ok "$m has one image line ghcr.io/luisehk/herrada-me:latest"; else bad "$m has $n image lines ghcr.io/luisehk/herrada-me:latest, expected 1"; fi
others="$(grep -E '^[[:space:]]*namespace:' "$m" | grep -vE 'namespace: herrada-me$' || true)"
if [ -z "$others" ]; then ok "$m names namespace herrada-me alone"; else bad "$m names another namespace: $(echo $others)"; fi
# Fixed strings, matched against whole lines with the indent stripped.
for want in 'automountServiceAccountToken: false' 'type: RuntimeDefault' 'allowPrivilegeEscalation: false' 'drop: ["ALL"]'; do
	n="$(sed 's/^[[:space:]]*//' "$m" | grep -cxF -- "$want")"
	if [ "$n" = 1 ]; then ok "$m sets $want"; else bad "$m has $n lines '$want', expected 1"; fi
done

# 3. app.mk.
if grep -nE 'origin[/ ]main' app.mk; then bad "app.mk still names origin main"; else ok "app.mk deploys from origin/master"; fi
# The recipe runs from its target line to the first blank line.
recipe="$(sed -n '/^copy_pull_secret:/,/^$/p' app.mk)"
if ! grep -qF 'create secret docker-registry ghcr-pull-secret' <<<"$recipe"; then
	bad "app.mk's copy_pull_secret does not create ghcr-pull-secret with kubectl create"
elif grep -qE '[[:space:]]apply([[:space:]]|$)' <<<"$recipe"; then
	bad "app.mk's copy_pull_secret runs kubectl apply (rentaventa-k8s ADR 0005: create only if absent)"
else
	ok "app.mk's copy_pull_secret creates ghcr-pull-secret and never applies it"
fi

echo "check-repo: $checks checks, $failed failed"
[ "$failed" -eq 0 ]
