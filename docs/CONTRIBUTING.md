Contributing
------------

In order to contribute, please fork this repo on Github and raise pull a request with your changes.

You can see a simple development/debugging workflow in the [debugging section](#debugging).


## Run The Tests

There are four types of testing/validation in the source code:

 1. Linting of syntactic code errors, and other Python style issues with [`pylint`](http://pylint.org)
 2. Typechecking of the python, based on the type-hints in the source using [`mypy`](http://mypy-lang.org)
 3. Unit testing via [`pytest`](https://docs.pytest.org/en/latest), by running all the [tests](./tests)
 4. Integration testing - which requires a local instance of Jira

The `Makefile` run the first three steps in order, when you invoke the `make` command on its own.
These three checks are also run on every pull request - and must pass for your code to mergeable.

You can invoke any individual stage directly with:

 1. `make lint`
 2. `make typecheck`
 3. `make test`
 4. `make integration`


## Integration Tests

In the `docker-compose.yml` there's an additional service named `jira`, which will create a real dev
instance of Jira, using a trial license.

The licence creation process is not currently automated, so you must do this manually with a valid
email address.

```
docker-compose up -d jira
```

Jira takes some time to start, so go make a cup of tea. You will be able to access this Jira in your
browser at http://localhost:8666.

The `Makefile` defines a few environment variables to configure the integration test run; you will
need to specify your Jira username/password; the host is assumed to be unchanged as `jira:8080` is
defined in `docker-compose.yml`.

|ENV variable|Default||
|-|-|-|
|`INT_HOST`|`jira:8080`|Hostname of the test Jira instance|
|`INT_USER`|`jirauser`|Jira test user login username|
|`INT_PASS`|`logmein`|Jira test user login password|

For further details on the internals of testing (mostly for developers), see
[the testing guide](./TESTING.md#integration-tests-in-docker).


## Debugging

The simplest way to debug before opening an issue or contributing is to run the application from
source code in a docker container, using the `test` image.

 1. Clone the source code to your machine

 2. Build the main & test docker images:

```
docker-compose build jira-offline
docker-compose build test
```

 3. Edit `docker-compose.yml` on line 5, to use the `-test` image:

```
jira-offline:
  image: mafrosis/jira-offline-test
```

 4. Add a breakpoint in the code with `import ipdb; ipdb.set_trace()`

 5. Run the main docker image, which will then break:

```
docker-compose run --rm jira-offline <CMD>
```
