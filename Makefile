# Create the database and load the bundled data (places + fuel stations). Runs offline.
.PHONY: setup
setup:
	python manage.py migrate
	python manage.py import_places
	python manage.py import_fuel_stations --offline

.PHONY: run
run:
	python manage.py runserver $(or $(PORT),8000)

# Execute tests with coverage.
.PHONY: run-tests
run-tests:
	coverage erase
	coverage run manage.py test $(ARGS)
	coverage report
	coverage html

.PHONY: test
test:
	python manage.py test -k $(filter-out $@,$(MAKECMDGOALS))

.PHONY: lint
lint:
	ruff check .
	ruff format --check .
	isort --check-only .
	mypy .

# Rebuild data/us_places.csv.gz from the US Census gazetteer (only needed to refresh it).
.PHONY: build-places
build-places:
	python scripts/build_places_dataset.py

%:
	@:
