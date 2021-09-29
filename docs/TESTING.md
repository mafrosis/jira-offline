Testing Guide
=============

There are four types of testing/validation in the source code:

 1. Typechecking of the python, based on the type-hints in the source using [`mypy`](http://mypy-lang.org)
 2. Linting of syntactic code errors, and other Python style issues with [`pylint`](http://pylint.org)
 3. Unit testing via [`pytest`](https://docs.pytest.org/en/latest), by running all the [tests](./tests)
 4. Integration testing - which requires a local instance of Jira

The `Makefile` run the first three steps in order, when you invoke the `make` command on its own.
These three checks are also run on every pull request - and must pass for your code to mergeable.

You can invoke any individual stage directly with:

 1. `make typecheck`
 2. `make lint`
 3. `make test`
 4. `make integration`


Type Hinting with mypy
----------------------


Linting with pylint
-------------------


Unit tests with pytest
----------------------


Integration tests in docker
---------------------------

Integration tests are completed via invocations of the `jira-offline` application in managed docker
containers, which connect to a live instance of Jira on `localhost`.


### Setting up the test Jira instance


### Note on the pytest fixtures

`jira_project` does setup via API calls

`run_in_docker` fires up a single docker image running `jira-offline`, with the passed CLI string.
For example:

```
run_in_docker(   ......
```


### Writing integration tests

The tests are written as normal `pytest` tests, in the directory `test/integration`. Add the following
decorator to ensure they are included in the integration test run, and skipped in the unit test run.

```
@pytest.mark.integration
```


### How to debug a failing integration test

A [remote debugger](https://github.com/ionelmc/python-remote-pdb) is included to enable you to
interactively debug a failing integration test. Drop the following line into the appropriate spot:

```
breakpoint()
```

Now, you can run the following in another shell window to attach to a PDB prompt in the executing
test run.


```
docker exec -it $(docker ps | grep jira-offline-integration-wrapper | cut -d\  -f 1) telnet localhost 4444
```

You can change the port via environment variable `REMOTE_PDB_PORT` in `docker-compose.yml`
