.PHONY: db-up db-down db-reset migrate run createsuperuser css css-watch

db-up:
	docker compose up -d db

db-down:
	docker compose down

db-reset:
	docker compose down -v
	docker compose up -d db

migrate:
	.venv/bin/python manage.py migrate

run:
	.venv/bin/python manage.py runserver 8001

createsuperuser:
	.venv/bin/python manage.py createsuperuser

css:
	npm run build:css

css-watch:
	npm run watch:css
