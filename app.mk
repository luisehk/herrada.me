# Deployment targets for herrada.me (RK-0029)
#
# Copied from luisehk/vim-puzzles app.mk at ee26ea7, with master for main, this
# site's names and no build args (the site has no build step).
# CD: `make cd` (bottom of this file) deploys one commit from a forge (vim-puzzles
# ADRs 0009 and 0010). Manual path:  make ci && make build && make push && make deploy TAG=<sha>

# Variables
APP_NAME = herrada-me
DOCKER_REGISTRY = ghcr.io/luisehk
REGISTRY_HOST = $(firstword $(subst /, ,$(DOCKER_REGISTRY)))
IMAGE_NAME = $(DOCKER_REGISTRY)/$(APP_NAME)
TAG ?= latest
DOCKERFILE = docker/Dockerfile
MANIFEST = k8s/deployment.yml
KUBE_NAMESPACE = herrada-me
DEPLOYMENT_NAME = herrada-me

# The kubeconfig. Every kubectl call in this file passes it as --kubeconfig,
# which beats kubectl's own lookup, so no other file is ever read (vim-puzzles ADR 0010).
#   CD_KUBECONFIG  the file, from the command line or the environment.
#                  `smithy deploy` passes it (Smithy SM-0003)
#   unset or empty ~/.kube/linode.yaml, the production kubeconfig
# KUBECONFIG, from the shell or the command line, changes nothing here, so a
# shell that exports a stale one still reaches the production cluster.
ifneq ($(strip $(CD_KUBECONFIG)),)
CD_KUBECONFIG_FROM := CD_KUBECONFIG
else
override CD_KUBECONFIG := $(HOME)/.kube/linode.yaml
CD_KUBECONFIG_FROM := the default
endif
KUBECTL = kubectl --kubeconfig "$(CD_KUBECONFIG)"

.PHONY: build-image tag-image build push deploy logs remote-shell status verify-deployment rollback scale delete-deployment copy_pull_secret

# Docker targets
build-image:
	@echo "Building Docker image..."
	docker build -f $(DOCKERFILE) -t $(APP_NAME):$(TAG) .

tag-image:
	@echo "Tagging Docker image..."
	docker tag $(APP_NAME):$(TAG) $(IMAGE_NAME):$(TAG)

build: build-image tag-image
	@echo "Docker image built and tagged successfully"

push:
	@echo "Pushing Docker image to registry..."
	docker push $(IMAGE_NAME):$(TAG)

# Kubernetes deployment targets
#
# The image tag is substituted into the manifest before apply, so a deploy is a
# single declarative apply and a single rollout. Applying the committed :latest
# and then re-pinning with `kubectl set image` would trigger two rollouts.
# There is no separate namespace step, as in cd-rollout below: the manifest's
# own Namespace document applies it, and rentaventa-k8s's deploy role creates it
# first (RK-0029 D2), so a first deploy with the scoped file works too.
deploy:
	@echo "Deploying $(IMAGE_NAME):$(TAG) to Kubernetes with $(CD_KUBECONFIG)..."
	@echo "Applying Kubernetes manifests..."
	set -o pipefail; sed "s|$(APP_NAME):latest|$(APP_NAME):$(TAG)|" $(MANIFEST) | $(KUBECTL) apply -f -
	@echo "Waiting for deployment to be ready..."
	$(KUBECTL) rollout status deployment/$(DEPLOYMENT_NAME) -n $(KUBE_NAMESPACE) --timeout=300s
	@echo "Deployment successful!"

# Utility targets
logs:
	$(KUBECTL) logs -f deployment/$(DEPLOYMENT_NAME) -n $(KUBE_NAMESPACE)

remote-shell:
	$(KUBECTL) exec -it deployment/$(DEPLOYMENT_NAME) -n $(KUBE_NAMESPACE) -- /bin/sh

status:
	@echo "Deployment status:"
	$(KUBECTL) get deployment $(DEPLOYMENT_NAME) -n $(KUBE_NAMESPACE)
	@echo "Pods:"
	$(KUBECTL) get pods -n $(KUBE_NAMESPACE) -l app=$(APP_NAME)
	@echo "Service:"
	$(KUBECTL) get service $(APP_NAME)-service -n $(KUBE_NAMESPACE)
	@echo "Ingress:"
	$(KUBECTL) get ingress $(APP_NAME)-ingress -n $(KUBE_NAMESPACE)
	@echo "Certificate:"
	$(KUBECTL) get certificate -n $(KUBE_NAMESPACE)

verify-deployment:
	@echo "Verifying deployment..."
	@$(KUBECTL) get deployment $(DEPLOYMENT_NAME) -n $(KUBE_NAMESPACE) -o json | \
		jq '.status.conditions[] | select(.type=="Available") | .status' | grep -q True && \
		echo "OK: deployment is available" || echo "FAIL: deployment is not available"
	@echo "Current image:"
	@$(KUBECTL) get deployment $(DEPLOYMENT_NAME) -n $(KUBE_NAMESPACE) \
		-o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'

# Real rollback: each revision pins a distinct immutable :<sha> image.
rollback:
	@echo "Rolling back deployment..."
	$(KUBECTL) rollout undo deployment/$(DEPLOYMENT_NAME) -n $(KUBE_NAMESPACE)
	$(KUBECTL) rollout status deployment/$(DEPLOYMENT_NAME) -n $(KUBE_NAMESPACE) --timeout=300s

scale:
	@read -p "Enter number of replicas: " replicas; \
	$(KUBECTL) scale deployment/$(DEPLOYMENT_NAME) -n $(KUBE_NAMESPACE) --replicas=$$replicas

delete-deployment:
	@echo "Deleting deployment..."
	$(KUBECTL) delete -f $(MANIFEST) --ignore-not-found=true
	@echo "Deployment deleted"

# One-time cluster setup (RK-0029 D2): copy ghcr-pull-secret from the vim-puzzles
# namespace. The scoped deploy file cannot read another namespace's Secret, so
# this runs with the operator file, named on the command line:
#   make copy_pull_secret CD_KUBECONFIG=$(HOME)/.kube/linode.yaml DRY_RUN=1
# Only the name and the namespace are kept from the source's metadata. The Secret
# goes from kubectl to python to kubectl on pipes and is never printed. DRY_RUN
# makes the apply a server-side dry run.
copy_pull_secret:
	@echo "Copying ghcr-pull-secret from vim-puzzles to $(KUBE_NAMESPACE) with $(CD_KUBECONFIG)$(if $(CD_DRY), (server-side dry run),)..."
	@set -o pipefail; $(KUBECTL) -n vim-puzzles get secret ghcr-pull-secret -o json \
		| python3 -I -c 'import json,sys; s=json.load(sys.stdin); s["metadata"]={"name":s["metadata"]["name"],"namespace":"$(KUBE_NAMESPACE)"}; print(json.dumps(s))' \
		| $(KUBECTL) apply $(if $(CD_DRY),--dry-run=server,) -f -

# ---------------------------------------------------------------------------
# CD from a forge: `make cd` (vim-puzzles ADRs 0009 and 0010; Smithy ADRs 0014
# and 0015, and the knobs of Smithy SM-0003's make cd contract).
#
# Builds, pushes and rolls out ONE immutable image for ONE commit, from a
# machine that holds a registry login and the production kubeconfig.
# Idempotent per SHA: an image already in the registry is not rebuilt, and
# applying the manifest that already pins it changes nothing.
#
# The gates (ci, review, qa) run before this and stamp the commit; `make cd`
# does not rerun them. It refuses anything but a clean checkout of a commit on
# origin/master, a kubeconfig for another cluster, and a cluster without the
# deployment. The image and the manifest come from the commit (git archive and
# git show), never from the working tree.
#
#   make cd                      # deploy HEAD
#   make cd SHA=<full sha>       # same, and assert HEAD is that commit
#   make cd DRY_RUN=1            # run the reads, print every write instead
#   make cd FORCE=1              # skip the clean-tree and origin/master checks
#   make cd REBUILD=1            # build :<sha> even when the registry has it
#   make cd CD_KUBECONFIG=<file> # the kubeconfig (see the top of this file)
#   make cd 2>&1 | tee <log>     # keeping the log is the caller's job
#
# DRY_RUN is any value but empty or 0, from the command line or the
# environment. FORCE counts only on the command line and only as 1: an
# exported FORCE is ignored. It never skips the SHA checks, the registry and
# cluster checks or the fence. REBUILD counts as 1 from either place.
# With SMITHY_DEPLOY_ID set (by `smithy deploy`), cd-rollout asks
# $SMITHY_URL/api/v1/deploys/$SMITHY_DEPLOY_ID just before the apply and
# refuses unless that deploy is running with a lease in the future.
# The last line of a real run is exactly
#   cd: ok sha=<40-hex> image=<image>:<sha> url=<url>
# and of a dry run `cd: dry run sha=<sha>`, so nothing reads a dry run as a deploy.
# ---------------------------------------------------------------------------
SHA ?= $(shell git rev-parse HEAD 2>/dev/null)
CD_EXPECT_SERVER ?= https://198.58.106.77:6443
CD_URL ?= https://herrada.me
CD_PLATFORM ?= linux/amd64
CD_ROLLOUT_TIMEOUT ?= 300s
CD_BUILDER = $(APP_NAME)-cd
CD_DRY := $(if $(filter-out 0,$(DRY_RUN)),1,)
CD_FORCE := $(if $(filter command line,$(origin FORCE)),$(filter 1,$(FORCE)),)
CD_REBUILD := $(filter 1,$(REBUILD))
# Pins the manifest at SHA: the committed :latest image line becomes :<sha>.
CD_MANIFEST = git show $(SHA):$(MANIFEST) | sed "s|$(APP_NAME):latest|$(APP_NAME):$(SHA)|"
# In a dry run, `run` prints a write instead of running it.
CD_RUN = run() { if [ -n "$(CD_DRY)" ]; then echo "cd: dry run, would run: $$*"; else "$$@"; fi; };
ifneq ($(CD_DRY),)
CD_BUILDING := cd: dry run, would build
else
CD_BUILDING := cd: building
endif

.PHONY: cd cd-preflight cd-image cd-rollout cd-verify
# The steps must run in order, even under `make -j`.
.NOTPARALLEL: cd

ifeq ($(CD_DRY),)
cd: cd-preflight cd-image cd-rollout cd-verify
	@echo "cd: ok sha=$(SHA) image=$(IMAGE_NAME):$(SHA) url=$(CD_URL)"
else
cd: cd-preflight cd-image cd-rollout
	@echo "cd: dry run sha=$(SHA)"
endif

# Read-only checks. Each failure names its fix and stops before anything is
# built, pushed or applied. FORCE=1 skips the clean-tree and origin/master
# checks and nothing else.
cd-preflight:
	@printf '%s' "$(SHA)" | grep -Eqx '[0-9a-f]{40}' \
		|| { echo "cd: SHA must be a full 40-character commit hash, got '$(SHA)'"; exit 1; }
	@test "$$(git rev-parse HEAD)" = "$(SHA)" \
		|| { echo "cd: working tree is at $$(git rev-parse HEAD), not $(SHA); check it out first"; exit 1; }
	@if [ -n "$(CD_DRY)" ]; then echo "cd: DRY_RUN=$(DRY_RUN): the reads run, every write is printed instead"; fi
	@if [ "$(origin FORCE)" = "environment" ]; then echo "cd: FORCE in the environment is ignored; it counts only on the command line"; fi
	@if [ -n "$${CD_ALLOW_UNMERGED:-}" ]; then echo "cd: CD_ALLOW_UNMERGED is no longer read; FORCE=1 on the command line replaces it"; fi
	@if [ -n "$$(git status --porcelain)" ]; then \
		if [ -n "$(CD_FORCE)" ]; then \
			echo "cd: WARNING FORCE=1: the working tree is dirty; the image and the manifest come from $(SHA) as committed"; \
		else \
			echo "cd: working tree is dirty; commit or stash first"; git status --short | head -n 10; exit 1; \
		fi; \
	fi
	@if [ -n "$(CD_FORCE)" ]; then \
		echo "cd: WARNING FORCE=1: skipping the origin/master check"; \
	else \
		git fetch -q origin master || { echo "cd: git fetch origin master failed"; exit 1; }; \
		git merge-base --is-ancestor $(SHA) origin/master \
			|| { echo "cd: $(SHA) is not on origin/master (FORCE=1 on the command line to override)"; exit 1; }; \
	fi
	@git show $(SHA):$(MANIFEST) 2>/dev/null | grep -qF '$(IMAGE_NAME):latest' \
		|| { echo "cd: $(MANIFEST) at $(SHA) has no $(IMAGE_NAME):latest image line to pin"; exit 1; }
	@docker info >/dev/null 2>&1 || { echo "cd: docker daemon not reachable"; exit 1; }
	@docker buildx version >/dev/null 2>&1 || { echo "cd: docker buildx is missing"; exit 1; }
	@grep -Eq '"(https://)?$(subst .,\.,$(REGISTRY_HOST))"' "$${DOCKER_CONFIG:-$$HOME/.docker}/config.json" 2>/dev/null \
		|| { echo "cd: no $(REGISTRY_HOST) login. Run: gh auth token | docker login $(REGISTRY_HOST) -u luisehk --password-stdin"; exit 1; }
	@echo "cd: kubeconfig $(CD_KUBECONFIG), from $(CD_KUBECONFIG_FROM)"
	@if [ -n "$${KUBECONFIG:-}" ] && [ "$$KUBECONFIG" != "$(CD_KUBECONFIG)" ]; then \
		echo "cd: KUBECONFIG=$$KUBECONFIG is ignored, every kubectl call uses $(CD_KUBECONFIG)"; fi
	@server="$$($(KUBECTL) config view --minify -o jsonpath='{.clusters[0].cluster.server}' 2>/dev/null)"; \
		test "$$server" = "$(CD_EXPECT_SERVER)" \
		|| { echo "cd: kubeconfig $(CD_KUBECONFIG) points at $${server:-nothing}, expected $(CD_EXPECT_SERVER)"; exit 1; }
	@err="$$($(KUBECTL) get deployment $(DEPLOYMENT_NAME) -n $(KUBE_NAMESPACE) -o name --request-timeout=10s 2>&1 >/dev/null)" \
		|| { echo "cd: cannot read deployment/$(DEPLOYMENT_NAME) in namespace $(KUBE_NAMESPACE) with $(CD_KUBECONFIG): $$(printf '%s' "$$err" | head -n 1 | cut -c1-200)"; \
			echo "cd: refusing before any write; a first deploy to a new cluster is make deploy TAG=<sha>"; exit 1; }
	@$(KUBECTL) -n $(KUBE_NAMESPACE) get secret ghcr-pull-secret -o name >/dev/null 2>&1 \
		|| echo "cd: WARNING ghcr-pull-secret missing in $(KUBE_NAMESPACE); new pods will ImagePullBackOff"
	@echo "cd: preflight ok sha=$(SHA) cluster=$(CD_EXPECT_SERVER)"

# One build, two tags, one push, and only when the registry has no :<sha> yet
# or REBUILD=1. A lookup error other than "not found" stops the run instead of
# rebuilding a tag that may exist. The build runs on the docker-container
# builder $(CD_BUILDER), created on first use, from a git archive of SHA, so
# untracked or modified files never reach the image.
cd-image: cd-preflight
	@set -o pipefail; $(CD_RUN) \
	err="$$(docker manifest inspect $(IMAGE_NAME):$(SHA) 2>&1 >/dev/null)"; rc=$$?; \
	if [ $$rc -eq 0 ] && [ -z "$(CD_REBUILD)" ]; then \
		echo "cd: $(IMAGE_NAME):$(SHA) already in the registry; skipping build (REBUILD=1 builds it again)"; exit 0; \
	elif [ $$rc -eq 0 ]; then \
		echo "$(CD_BUILDING) $(IMAGE_NAME):$(SHA) again for $(CD_PLATFORM) (REBUILD=1)"; \
	elif printf '%s' "$$err" | grep -qiE 'manifest unknown|no such manifest|not found'; then \
		echo "$(CD_BUILDING) $(IMAGE_NAME):$(SHA) for $(CD_PLATFORM)"; \
	else \
		echo "cd: cannot look up $(IMAGE_NAME):$(SHA): $$(printf '%s' "$$err" | head -n 1 | cut -c1-200)"; exit 1; \
	fi; \
	if ! docker buildx inspect $(CD_BUILDER) >/dev/null 2>&1; then \
		run docker buildx create --name $(CD_BUILDER) --driver docker-container || exit 1; \
	fi; \
	if [ -n "$(CD_DRY)" ]; then src="<git archive of $(SHA)>"; else \
		src="$$(mktemp -d)" && trap 'rm -rf "$$src"' EXIT && git archive --format=tar $(SHA) | tar -x -C "$$src" \
			|| { echo "cd: git archive of $(SHA) failed"; exit 1; }; \
	fi; \
	run docker buildx build --builder $(CD_BUILDER) --platform $(CD_PLATFORM) -f "$$src/$(DOCKERFILE)" \
		-t $(IMAGE_NAME):$(SHA) -t $(IMAGE_NAME):latest --push "$$src"

# The fence, then the apply. With SMITHY_DEPLOY_ID set, Smithy is asked just
# before the apply whether this deploy still runs and holds its lease; any
# other answer, and no answer, refuses. The token reaches curl on stdin as a
# header line; the shell expands it, not make, so it is in no process's argv.
# The apply is the same substitution as `deploy`, without its separate
# namespace step: the manifest's own Namespace document creates it, and
# applying two different Namespace configs made every run report it as
# `configured`. One apply and one rollout, so a rerun on the same SHA reports
# every resource `unchanged`. A stuck rollout leaves the old pods serving
# (surge 1, unavailable 0) and prints what cd.yml printed on failure.
cd-rollout: cd-image
	@if [ -n "$${SMITHY_DEPLOY_ID:-}" ]; then \
		printf '%s' "$$SMITHY_DEPLOY_ID" | grep -Eqx '[A-Za-z0-9._-]+' \
			|| { echo "cd: SMITHY_DEPLOY_ID may hold only letters, digits, '.', '_' and '-'; refusing to apply"; exit 1; }; \
		[ -n "$${SMITHY_URL:-}" ] || { echo "cd: SMITHY_DEPLOY_ID is set but SMITHY_URL is not; refusing to apply"; exit 1; }; \
		url="$${SMITHY_URL%/}/api/v1/deploys/$$SMITHY_DEPLOY_ID"; \
		body="$$( { if [ -n "$${SMITHY_TOKEN:-}" ]; then printf 'Authorization: Bearer %s\n' "$$SMITHY_TOKEN"; fi; } \
			| curl -sS --fail --max-time 10 -H @- "$$url")" \
			|| { echo "cd: cannot read $$url; refusing to apply"; exit 1; }; \
		printf '%s' "$$body" | python3 -I scripts/check_deploy_lease "$$SMITHY_DEPLOY_ID" "$(SHA)" || exit 1; \
	fi
ifneq ($(CD_DRY),)
	@echo "cd: dry run, would run: git show $(SHA):$(MANIFEST) | sed 's|$(APP_NAME):latest|$(APP_NAME):$(SHA)|' | $(KUBECTL) apply -f -"
	@set -o pipefail; $(CD_MANIFEST) | grep -E '^[[:space:]]*image:' | sed 's/^[[:space:]]*/cd: dry run, the manifest would pin /'
	@echo "cd: dry run, would wait for deployment/$(DEPLOYMENT_NAME) to roll out and check $(CD_URL)/health"
else
	@echo "cd: applying $(MANIFEST) at $(SHA), pinned to $(IMAGE_NAME):$(SHA)"
	@set -o pipefail; $(CD_MANIFEST) | $(KUBECTL) apply -f - || { echo "cd: kubectl apply failed"; exit 1; }
	@$(KUBECTL) rollout status deployment/$(DEPLOYMENT_NAME) -n $(KUBE_NAMESPACE) --timeout=$(CD_ROLLOUT_TIMEOUT) \
		|| { echo "cd: rollout did not complete; the old pods keep serving"; \
			$(KUBECTL) get pods -n $(KUBE_NAMESPACE) -l app=$(APP_NAME); \
			$(KUBECTL) describe deployment $(DEPLOYMENT_NAME) -n $(KUBE_NAMESPACE) | tail -n 25; \
			$(KUBECTL) logs -n $(KUBE_NAMESPACE) -l app=$(APP_NAME) --tail=50 || true; \
			echo "cd: fix forward, or make rollback"; exit 1; }
endif

# The deployment must pin this SHA, and the live domain must answer /health.
# Read-only, so it also runs on its own: make cd-verify SHA=<sha>.
cd-verify:
	@running="$$($(KUBECTL) get deployment $(DEPLOYMENT_NAME) -n $(KUBE_NAMESPACE) \
		-o jsonpath='{.spec.template.spec.containers[0].image}')"; \
		test "$$running" = "$(IMAGE_NAME):$(SHA)" \
		|| { echo "cd: deployment runs $${running:-nothing}, expected $(IMAGE_NAME):$(SHA)"; exit 1; }
	@echo "cd: deployment image is $(IMAGE_NAME):$(SHA)"
	@$(KUBECTL) get deployment $(DEPLOYMENT_NAME) -n $(KUBE_NAMESPACE)
	@$(KUBECTL) get pods -n $(KUBE_NAMESPACE) -l app=$(APP_NAME)
	@$(KUBECTL) get service $(APP_NAME)-service -n $(KUBE_NAMESPACE)
	@$(KUBECTL) get ingress $(APP_NAME)-ingress -n $(KUBE_NAMESPACE)
	@for i in 1 2 3 4 5 6; do \
		code="$$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 $(CD_URL)/health || true)"; \
		if [ "$$code" = "200" ]; then echo "cd: $(CD_URL)/health -> 200"; exit 0; fi; \
		echo "cd: $(CD_URL)/health -> $$code, retrying in 5s"; sleep 5; \
	done; echo "cd: $(CD_URL)/health did not return 200"; exit 1
