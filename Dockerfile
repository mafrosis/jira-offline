ARG PYTHON_VERSION=3.7
FROM python:${PYTHON_VERSION}-slim

RUN pip install ipdb
WORKDIR /app

RUN apt-get update && apt-get install -y vim
ENV EDITOR=vim

ADD requirements.txt requirements-dev.txt /app/
RUN pip install -r requirements-dev.txt

ADD README.md LICENSE MANIFEST.in setup.py /app/
ADD jira_cli /app/jira_cli
RUN pip install -e .

ENTRYPOINT ["jiracli"]
