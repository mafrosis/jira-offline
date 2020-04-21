ARG PYTHON_VERSION=3.7
FROM python:${PYTHON_VERSION}-slim

WORKDIR /app

RUN apt-get update && apt-get install -y vim
ENV EDITOR=vim

ADD requirements.txt /app/
RUN pip install -r requirements.txt

ADD README.md LICENSE MANIFEST.in setup.py /app/
ADD jira_cli /app/jira_cli
RUN pip install -e .

ENTRYPOINT ["jira"]
