.PHONY=full_fresh_start generate_docu stop ragify

full_fresh_start:
	@echo "Docu GG Ez starting to build"
	@docker compose down --remove-orphans
	@docker compose pull
	@docker compose up -d --build

ragify:
	@echo "Docu GG Ez starting to build"
	@docker compose down --remove-orphans
	@docker compose pull
	@docker compose up --build
	@docker compose exec app python /app/ingest.py

generate_docu:
	@echo "Docu GG Ez starting to build"
	@docker compose down --remove-orphans
	@docker compose pull
	@docker compose up --build
	@docker compose exec app python /app/docume.py

stop:
	@echo "Stopping all"
	@docker compose down