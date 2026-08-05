FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    AGENT_HOST=0.0.0.0 \
    AGENT_PORT=18010

WORKDIR /app

RUN groupadd --system resumeagent \
    && useradd --system --gid resumeagent --create-home resumeagent

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --no-cache-dir .

USER resumeagent
EXPOSE 18010

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import json,urllib.request; assert json.load(urllib.request.urlopen('http://127.0.0.1:18010/api/health', timeout=3))['ok']"

CMD ["python", "-m", "resume_campaign_agent"]
