# Variables for integration testing
INT_HOST?=locahost
INT_USER?=jirauser
INT_PASS?=logmein


.PHONY: all
all: typecheck lint test
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
		--hostname=$(INT_HOST) \
		--username=$(INT_USER) \
		--password=$(INT_PASS) \
		--cwd=$$(pwd) \
		test/integration

.PHONY: lint
lint:
	docker-compose run --rm --entrypoint=pylint test jira_offline/
	docker-compose run --rm --entrypoint=pylint test --rcfile=test/.pylintrc test/

.PHONY: typecheck
typecheck:
	docker-compose run --rm test --mypy jira_offline/


.PHONY: clean
clean:
	rm -rf build dist

.PHONY: package
package: clean
	python3 -m pip install --upgrade setuptools wheel
	rm -rf jira_offline.egg-info dist
	python3 setup.py sdist bdist_wheel

.PHONY: publish-pypi
publish-pypi:
	docker build -f Dockerfile.twine -t mafrosis/twine .
	docker run --rm -v $$(pwd)/dist:/dist:ro \
		mafrosis/twine \
		check /dist/*
	docker run --rm -v $$(pwd)/dist:/dist:ro \
		-e TWINE_USERNAME -e TWINE_PASSWORD \
		mafrosis/twine \
		upload --verbose /dist/*

.PHONY: publish-docker
publish-docker:
	echo "$(GITHUB_TOKEN)" | docker login -u mafrosis --password-stdin docker.pkg.github.com
	docker tag mafrosis/jira-offline docker.pkg.github.com/mafrosis/jira-offline/jira-offline:$(TAG)
	docker push docker.pkg.github.com/mafrosis/jira-offline/jira-offline:$(TAG)

.PHONY: version
version:
	@python3 -c 'from pkg_resources import *; print(require("jira-offline")[0].version)'

.PHONY: is_prerelease
is_prerelease:
	@python3 -c 'from pkg_resources import *; print(str(parse_version(require("jira-offline")[0].version).is_prerelease).lower())'
