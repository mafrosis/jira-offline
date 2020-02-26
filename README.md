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


How To Use
----------

**NB**: The following examples assume `jiracli` is available in `$PATH`

### How to configure a new Jira project

Use `clone` to add a project:

    jiracli clone PROJ


Extending This Tool
-------------------

### Adding a new field from Jira

It's very easy to include a new field from Jira. Two steps are required:

  1. Include the field in the Issue model in [models.py](./jira_cli/models.py)
  2. Include the field in the `jiraapi_object_to_issue` method in [sync.py](./jira_cli/sync.py)
  3. Include the field in the `issue_to_jiraapi_update` method in [sync.py](./jira_cli/sync.py), if
     it can be written back to Jira
