Git-like CLI for using Jira offline
=================

Work offline and sync your changes back to Jira later. Create issues, modify issues, view stats,
run Jira health queries.. All from a friendly git-like CLI.


Installation
------------

A few options exist:

  1. Use the quickstart to pull and run a docker image (see #quickstart)
  2. Install with pip into your current user account
  3. Clone the source code and use docker compose

### Quickstart

Using the docker image published on Github, the following will get you going very quickly:

    docker pull docker.pkg.github.com/mafrosis/jiracli/jiracli:dev
    docker run --rm -it docker.pkg.github.com/mafrosis/jiracli/jiracli:dev

### Install with pip

    pip install git+https://github.com/mafrosis/jiracli.git@master

### Clone and use compose

    git clone https://github.com/mafrosis/jiracli.git
    cd jiracli
    docker-compose build jiracli
    docker-compose run --rm jiracli


Known Limitations
-----------------

* Currently, you can't change the state of an issue (eg. In Progress -> Done)
* It's slow. Reading and writing all data to a single JSONL file is inefficient, and the quantity of
  serialize/deserialize operations can surely be optimised.
* No support for the same project key from two different Jiras (an edge-case at this stage)


Quick Start
-----------

**NB**: The following examples assume `jiracli` is available in `$PATH`

### Clone

The `clone` command is used to to setup a new project, which takes a single URI describing your
project.

### Authentication to Jira

There are two auth options, basic and oAuth.

#### Basic Auth

Basic auth is quick and takes your existing username and password. Beware that this will *write your
password into the config file on disk*.

    jiracli clone --username benji https://jira.atlassian.com/PROJ

You will be prompted for your password.

#### oAuth

oAuth is preferred, as it's token based and doesn't require your password. However it requires the
setup of an `Application Link` on the Jira server.

    jiracli clone --oauth-private-key=applink.pem https://jira.atlassian.com/PROJ


How To Use
----------

**NB**: The following examples assume `jiracli` is available in `$PATH`

### How to configure a new Jira project

Use `clone` to add a project:

    jiracli clone https://jira.atlassian.com/PROJ


Extending This Tool
-------------------

### Adding a new field from Jira

It's very easy to include a new field from Jira. Two steps are required:

  1. Include the field in the Issue model in [models.py](./jira_cli/models.py)
  2. Include the field in the `jiraapi_object_to_issue` method in [sync.py](./jira_cli/sync.py)
  3. Include the field in the `issue_to_jiraapi_update` method in [sync.py](./jira_cli/sync.py), if
     it can be written back to Jira
