# herrada.me Makefile (RK-0029)
# The site is index.html, style.css and images/, with no build step. GitHub
# Pages serves them until RK-0029's step D4, and the k3s node serves the same
# files from the nginx image in docker/. The local gate and any future remote
# gate must not drift: CI == `make ci`.

.PHONY: help ci ci-check ci-image ci-nginx ci-smoke

SHELL := /bin/bash
.DEFAULT_GOAL := help

# The image `make ci` builds and tests. Local only, never pushed.
CI_IMAGE ?= herrada-me:ci

help:
	@echo "Available targets:"
	@echo "  make ci               - Repo checks, image build, nginx -t, container smoke on 127.0.0.1"
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

ci-image:
	docker build -f docker/Dockerfile -t $(CI_IMAGE) .

ci-nginx: ci-image
	docker run --rm --entrypoint nginx $(CI_IMAGE) -t

# T-RK-29-1: the container on 127.0.0.1, a free port from 8650 to 8659.
ci-smoke: ci-image
	@bash scripts/smoke.sh $(CI_IMAGE)

ci: ci-check ci-image ci-nginx ci-smoke
	@echo "CI checks completed successfully"

# Docker build + k3s deploy targets (build, push, deploy, cd, rollback, status, logs).
# Included last, and .DEFAULT_GOAL is pinned above, so `make` stays `make help`.
-include app.mk
