.PHONY: help start stop restart update sh logo test
.DEFAULT := help

MAKEFILE_PATH := $(abspath $(lastword $(MAKEFILE_LIST)))
CURRENT_DIR := $(dir $(MAKEFILE_PATH))
HASS := $$(cat docker-compose.yaml | grep container_name | tr ':' ' ' | awk '{ print $$2 }')

help:
	@awk 'BEGIN {FS = ":.*##"; printf "\n\033[1mUsage:\n  make \033[36m<target>\033[0m\n"} \
	/^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-40s\033[0m %s\n", $$1, $$2 } /^##@/ \
	{ printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Home Assistant

start: ## Start
	docker compose up -d
	@echo "\nOpen:\033[36m http://localhost:8123\033[0m\n"

stop: ## Stop
	docker stop $(HASS)

restart: stop start ## Restart

sh: ## Go inside HA container
	docker exec -it $(HASS) /bin/bash

##@ Development

logo: ## Generate PNG logo assets from SVG (requires ImageMagick)
	magick assets/logo.svg -resize 128x128 assets/logo.png
	magick assets/logo.svg -resize 256x256 assets/logo@2x.png

test: ## Run integration tests in the Home Assistant Docker image
	docker exec $(HASS) python -m pytest -p no:cacheprovider /tests
