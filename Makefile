COMPOSE = podman compose -f deploy/compose.yaml

.PHONY: up down ps logs test test-all go-test image go-build dispatcher seed chat

up:        ## start the control plane (postgres, nats, letta)
	$(COMPOSE) up -d

down:      ## stop the control plane
	$(COMPOSE) down

ps:        ## show service status
	$(COMPOSE) ps

logs:      ## tail service logs
	$(COMPOSE) logs -f

test:      ## run python unit tests (no services needed)
	cd agents/calliope && uv run pytest -v -m "not integration"

test-all:  ## run python tests incl. integration (services must be up)
	cd agents/calliope && uv run pytest -v

go-test:   ## run dispatcher tests
	cd dispatcher && go test ./...

image:     ## build the hermetic agent image
	podman build -t calliope-agent:latest agents/calliope

go-build:  ## build the dispatcher binary
	cd dispatcher && go build -o bin/dispatcher .

dispatcher: go-build image  ## run the dispatcher (drains iris.tasks.calliope)
	cd dispatcher && CALLIOPE_IMAGE=calliope-agent:latest ./bin/dispatcher

seed:      ## seed the voice style guide from mycelium_prod
	cd agents/calliope && uv run calliope seed

chat:      ## open an interactive session with Calliope
	cd agents/calliope && uv run calliope chat
