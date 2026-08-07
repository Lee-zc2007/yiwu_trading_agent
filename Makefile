.PHONY: install init dev test build train up down

install:
	python -m pip install -r backend/requirements.txt
	cd frontend && npm install

init:
	python scripts/init_data.py

dev:
	@echo "Run scripts/start_windows.ps1 on Windows or scripts/start.sh on Linux/macOS"

test:
	python -m pytest backend/tests -q

build:
	cd frontend && npm run build

train:
	python -m ml.training.train_isolation_forest

up:
	docker compose up --build

down:
	docker compose down
