# herrada.me Makefile (RK-0029, HM-0002)
# The site is three pages, style.css, script.js, fonts/ and assets/. The pages
# are written by build/build.py from build/counts.json and committed, so
# nothing builds at run time. GitHub Pages serves them until it goes off on
# 2026-12-02, and the k3s node serves the same files from the nginx image in
# docker/. The local gate and any future remote gate must not drift:
# CI == `make ci`.

.PHONY: help ci ci-check ci-site pages ci-image ci-nginx ci-smoke

SHELL := /bin/bash
.DEFAULT_GOAL := help

# The image `make ci` builds and tests. Local only, never pushed. The tag names
# the checkout, so two worktrees running `make ci` at once never test each
# other's image.
CI_IMAGE ?= herrada-me:ci-$(shell basename "$(CURDIR)" | tr -c 'A-Za-z0-9_.\n-' '-')

help:
	@echo "Available targets:"
	@echo "  make ci               - Repo checks, pages vs a rebuild, site tests, image build, nginx -t, container smoke on 127.0.0.1"
	@echo "  make pages            - Rewrite the three pages from build/counts.json (commit the result)"
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

# What GitHub Pages would publish, and the manifest and app.mk invariants.
ci-check:
	@bash scripts/check-repo.sh

# The committed pages must equal a rebuild of build/counts.json, and the site
# tests (build/test_site.py) must pass: content rules, no outside requests,
# noindex, links, folds, fonts and their licences. Python's standard library
# only; -B keeps __pycache__ out of the tree.
ci-site:
	python3 -B build/build.py --check
	python3 -B -m unittest discover -s build -p 'test_*.py'

pages:
	python3 -B build/build.py

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
