.PHONY: all
all: lint typecheck test
	@true

.PHONY: test
test:
	docker-compose run --rm test \
		-m 'not integration' \
		--cov=jira_offline --cov-report term --cov-report html:cov_html \
		--disable-pytest-warnings \
		test/

.PHONY: integration
integration:
	docker-compose run --rm test \
		-m 'integration' \
		--hostname=locke:8666 \
		--username=blackm \
		--password=eggseggs \
		--cwd=$$(pwd) \
		test/integration

.PHONY: lint
lint:
	docker-compose run --rm --entrypoint=pylint test jira_offline/
	docker-compose run --rm --entrypoint=pylint test --rcfile=test/.pylintrc test/

.PHONY: typecheck
typecheck:
	docker-compose run --rm test --mypy --mypy-ignore-missing-imports jira_offline/


.PHONY: package
package:
	python3 -m pip install --upgrade setuptools wheel
	rm -rf jira_offline.egg-info dist
	python3 setup.py sdist bdist_wheel

.PHONY: publish
publish:
	docker build -f Dockerfile.twine -t mafrosis/twine .
	docker run --rm -v $$(pwd)/dist:/dist:ro \
		mafrosis/twine \
		check /dist/*
	docker run --rm -v $$(pwd)/dist:/dist:ro \
		-e TWINE_USERNAME -e TWINE_PASSWORD \
		mafrosis/twine \
		upload /dist/*

.PHONY: version
version:
	@python3 -c 'from pkg_resources import *; print(require("jira-offline")[0].version)'

.PHONY: is_prerelease
is_prerelease:
	@python3 -c 'from pkg_resources import *; print(str(parse_version(require("jira-offline")[0].version).is_prerelease).lower())'
