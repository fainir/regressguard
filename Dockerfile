FROM python:3.13-slim

WORKDIR /app

COPY eval_runner/ ./eval_runner/
COPY webui/ ./webui/

RUN mkdir -p /data
ENV REGRESSGUARD_DB=/data/regressguard.db
ENV REGRESSGUARD_HOST=0.0.0.0
ENV REGRESSGUARD_PORT=8787
ENV PYTHONUNBUFFERED=1

EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8787/health').status==200 else 1)"

CMD ["python", "-m", "eval_runner.server"]
