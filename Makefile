.PHONY: install up down logs test

install:
	uv sync

up:
	DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1 docker compose up -d

down:
	docker compose down -v

logs:
	docker compose logs -f

test:
	docker compose run --rm media pytest
