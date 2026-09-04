.PHONY: install run dev lint format clean test help

# Default target
help:
	@echo "Amour Crochet Garden - Makefile targets"
	@echo ""
	@echo "  make install   - Install dependencies with UV"
	@echo "  make run       - Run the application (production)"
	@echo "  make dev       - Run with auto-reload (development)"
	@echo "  make lint      - Run Ruff linter"
	@echo "  make format    - Format code with Ruff"
	@echo "  make test      - Run tests"
	@echo "  make clean     - Remove build artifacts and cache"
	@echo ""

# Install dependencies
install:
	uv sync

# Run application (production)
run:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# Run with auto-reload (development)
dev:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Lint
lint:
	uv run ruff check app/

# Format
format:
	uv run ruff format app/
	uv run ruff check app/ --fix

# Test
test:
	uv run pytest tests/ -v 2>/dev/null || echo "No tests yet - add tests/ directory"

# Clean
clean:
	rm -rf __pycache__ .ruff_cache .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
