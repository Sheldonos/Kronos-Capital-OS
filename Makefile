.PHONY: bootstrap install genesis build start launch stop restart logs health test lint audit release
bootstrap:
	bash scripts/bootstrap_upstream.sh
install:
	python -m pip install -e ".[dev,marketdata,coinbase]"
genesis:
	python -m kcos.genesis
build:
	docker compose build
start:
	docker compose up -d
launch: build start
	@echo "KCOS is starting. Open http://127.0.0.1:8080 for Genesis setup."
stop:
	docker compose down
restart:
	docker compose restart
logs:
	docker compose logs -f --tail=200
health:
	curl -fsS http://127.0.0.1:8080/health | python -m json.tool
test:
	python -m pytest -q
lint:
	python -m compileall -q kcos tests
audit: lint test
	KCOS_RELEASE_DIR=dist python scripts/build_release.py
	python scripts/release_audit.py
release: audit
