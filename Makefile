.PHONY: install project build check-dist package-install lint

install:
	uv sync

project:
	uv run valutatrade-hub

build:
	uv build

check-dist:
	uvx twine check dist/*

package-install:
	uv tool install --force dist/*.whl

lint:
	uv run ruff check .
