.PHONY: db-up db-down db-reset migrate run createsuperuser

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
