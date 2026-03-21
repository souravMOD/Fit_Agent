.PHONY: setup run bot track test clean docker-up docker-down

setup:
	python -m venv .venv
	. .venv/bin/activate && pip install -e ".[dev]"
	ollama pull llava:7b
	ollama pull llama3.1:8b

run:
	streamlit run scripts/app.py

bot:
	python scripts/telegram_bot.py

track:
	mlflow ui --port 5000

test:
	pytest tests/

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

clean:
	rm -rf .venv __pycache__ mlruns data/fitagent.db