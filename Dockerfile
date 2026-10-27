FROM python:3.13-slim

WORKDIR /app

# Install the package with both provider SDKs so --provider anthropic/openai work in the image.
COPY pyproject.toml README.md LICENSE ./
COPY eval_runner/ ./eval_runner/
RUN pip install --no-cache-dir ".[all]"

RUN mkdir -p /data
ENV REGRESSGUARD_DB=/data/regressguard.db
ENV REGRESSGUARD_HOST=0.0.0.0
ENV REGRESSGUARD_PORT=8787
ENV PYTHONUNBUFFERED=1

EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import os,sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('REGRESSGUARD_PORT', '8787'), timeout=2).status == 200 else 1)"

# Default: the web UI / HTTP API. For CI runs, override with `regressguard --prompt ... --cases ...`.
CMD ["regressguard-server"]
