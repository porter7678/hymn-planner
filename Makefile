.PHONY: run stop test

run:
	uv run flask --app app run

stop:
	-lsof -ti :5000 | xargs kill

test:
	uv run pytest -v
