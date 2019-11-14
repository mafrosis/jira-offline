FROM python:3.7

RUN pip install ipdb
WORKDIR /app

ADD README.md LICENSE MANIFEST.in requirements.txt Dockerfile setup.py /app/
ADD jira_cli /app/jira_cli
RUN pip install -e .

ENTRYPOINT ["jira"]
