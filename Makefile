# herrada.me Makefile (RK-0029, HM-0002)
# The site is three pages, style.css, script.js, images/, fonts/ and assets/.
# scripts/build.py writes the pages from src/site.json (`make site`) and they
# are committed, so nothing builds at run time. GitHub Pages serves the files
# until RK-0029's step D4, and the k3s node serves the same files from the
# nginx image in docker/. The local gate and any future remote gate must not
# drift: CI == `make ci`.

.PHONY: help site ci ci-check ci-site ci-image ci-nginx ci-smoke

SHELL := /bin/bash
.DEFAULT_GOAL := help

# The image `make ci` builds and tests. Local only, never pushed.
CI_IMAGE ?= herrada-me:ci

help:
	@echo "Available targets:"
	@echo "  make site             - Write index.html, how-i-build.html and 404.html from src/site.json"
	@echo "  make ci               - Repo checks, site checks and tests, image build, nginx -t, container smoke on 127.0.0.1"
	@echo ""
	@echo "Deploy (app.mk):"
	@echo "  make cd               - Deploy HEAD from the forge: build + push :<sha>, roll out, check /health"
	@echo "                          (CD_KUBECONFIG, DRY_RUN, FORCE=1, REBUILD=1, SHA=, SMITHY_DEPLOY_ID; see app.mk)"
	@echo "  make build            - Build + tag the Docker image"
	@echo "  make push             - Push the image to ghcr.io/luisehk/herrada-me"
	@echo "  make deploy           - Apply k8s manifests and roll out (TAG=<sha> to pin)"
	@echo "  make status           - Deployment, pods, service, ingress, certificate"
	@echo "  make logs             - Tail deployment logs"
	@echo "  make rollback         - Roll back to the previous revision"
	@echo ""
	@echo "One-time cluster setup:"
	@echo "  make copy_pull_secret - Copy ghcr-pull-secret from the vim-puzzles namespace (operator file, DRY_RUN=1 first)"

# Write the pages from the data file. Commit them with src/site.json.
site:
	python3 -B scripts/build.py

# What GitHub Pages would publish, and the manifest and app.mk invariants.
ci-check:
	@bash scripts/check-repo.sh

# HM-0002: the pages match src/site.json, the site checks (content rules, no
# third-party request, noindex on a preview, links, the first screen, the Bumpy
# switch, the font) and the catch replay. Standard library Python and Node only.
ci-site:
	python3 -B scripts/build.py --check
	python3 -B -m unittest discover -s tests -p 'test_*.py'
	node --test tests/catch.test.js

ci-image:
	docker build -f docker/Dockerfile -t $(CI_IMAGE) .

ci-nginx: ci-image
	docker run --rm --entrypoint nginx $(CI_IMAGE) -t

# T-RK-29-1: the container on 127.0.0.1, a free port from 8650 to 8659.
ci-smoke: ci-image
	@bash scripts/smoke.sh $(CI_IMAGE)

ci: ci-check ci-site ci-image ci-nginx ci-smoke
	@echo "CI checks completed successfully"

# Docker build + k3s deploy targets (build, push, deploy, cd, rollback, status, logs).
# Included last, and .DEFAULT_GOAL is pinned above, so `make` stays `make help`.
-include app.mk
