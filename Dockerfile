ARG PYTHON_VERSION=3.7
FROM python:$PYTHON_VERSION

RUN pip install ipdb
WORKDIR /app

RUN apt-get update && apt-get install -y vim
ENV EDITOR=vim

ADD README.md LICENSE MANIFEST.in requirements.txt setup.py /app/
ADD jira_cli /app/jira_cli
RUN pip install -e .

ADD requirements-dev.txt /app/
RUN pip install -r requirements-dev.txt

ENTRYPOINT ["jira"]
