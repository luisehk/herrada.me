#!/usr/bin/env bash
# Static checks for `make ci` (RK-0029). Nothing here talks to a cluster.
#
#   1. GitHub Pages publishes the site alone. Jekyll skips paths with a part
#      that starts with '.' or '_' and the names _config.yml excludes; every
#      other tracked file publishes, and each must be CNAME, index.html,
#      style.css or a file under images/.
#   2. k8s/deployment.yml has no leading document marker (Jekyll would read it
#      as front matter), keeps the one image line `make cd` pins, and names
#      the herrada-me namespace alone. The pod keeps its hardening: no
#      ServiceAccount token, the RuntimeDefault seccomp profile and no
#      privilege escalation.
#   3. app.mk deploys from master: no origin/main is left from vim-puzzles.
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
	CNAME | index.html | style.css | images/*) ;;
	*) bad "GitHub Pages would publish $f; add it to _config.yml's exclude list" ;;
	esac
done < <(git ls-files)
for f in CNAME index.html style.css; do
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
for want in 'automountServiceAccountToken: false' 'type: RuntimeDefault' 'allowPrivilegeEscalation: false'; do
	n="$(grep -cE "^[[:space:]]*$want\$" "$m")"
	if [ "$n" = 1 ]; then ok "$m sets $want"; else bad "$m has $n lines '$want', expected 1"; fi
done

# 3. app.mk.
if grep -nE 'origin[/ ]main' app.mk; then bad "app.mk still names origin main"; else ok "app.mk deploys from origin/master"; fi

echo "check-repo: $checks checks, $failed failed"
[ "$failed" -eq 0 ]
