.PHONY: help setup test lint fmt

help:
	@echo "Prism (hackathon) commands:"
	@echo "  make setup   # install dependencies (auto-detect)"
	@echo "  make test    # run test suite (auto-detect)"
	@echo "  make lint    # run linter (auto-detect)"
	@echo "  make fmt     # run formatter (auto-detect)"

setup:
	@set -e; \
	did_any=0; \
	if [ -f package.json ]; then \
		did_any=1; \
		if command -v pnpm >/dev/null 2>&1; then pnpm install; \
		elif command -v npm >/dev/null 2>&1; then npm install; \
		else echo "No Node package manager found (pnpm/npm)."; exit 1; fi; \
	fi; \
	if [ -f pyproject.toml ]; then \
		did_any=1; \
		python3 -m pip install -e '.[dev]'; \
	fi; \
	if [ $$did_any -eq 0 ]; then \
		echo "No supported project type detected (package.json/pyproject.toml)."; exit 1; \
	fi

test:
	@set -e; \
	did_any=0; \
	if [ -f package.json ]; then \
		did_any=1; \
		if command -v pnpm >/dev/null 2>&1; then pnpm test; \
		elif command -v npm >/dev/null 2>&1; then npm test; \
		else echo "No Node package manager found (pnpm/npm)."; exit 1; fi; \
	fi; \
	if [ -f pyproject.toml ]; then \
		did_any=1; \
		python3 -m pytest -q; \
	fi; \
	if [ $$did_any -eq 0 ]; then \
		echo "No supported project type detected (package.json/pyproject.toml)."; exit 1; \
	fi

lint:
	@set -e; \
	did_any=0; \
	if [ -f package.json ]; then \
		did_any=1; \
		if command -v pnpm >/dev/null 2>&1; then pnpm lint; \
		elif command -v npm >/dev/null 2>&1; then npm run lint; \
		else echo "No Node package manager found (pnpm/npm)."; exit 1; fi; \
	fi; \
	if [ -f pyproject.toml ]; then \
		did_any=1; \
		python3 -m ruff check .; \
	fi; \
	if [ $$did_any -eq 0 ]; then \
		echo "No lint target configured yet."; exit 1; \
	fi

fmt:
	@set -e; \
	did_any=0; \
	if [ -f package.json ]; then \
		did_any=1; \
		if command -v pnpm >/dev/null 2>&1; then pnpm fmt; \
		elif command -v npm >/dev/null 2>&1; then npm run fmt; \
		else echo "No Node package manager found (pnpm/npm)."; exit 1; fi; \
	fi; \
	if [ -f pyproject.toml ]; then \
		did_any=1; \
		python3 -m ruff format .; \
	fi; \
	if [ $$did_any -eq 0 ]; then \
		echo "No fmt target configured yet."; exit 1; \
	fi
