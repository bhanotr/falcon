FROM docker.io/library/python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir "litellm[proxy]"
COPY litellm_config.yaml /app/litellm_config.yaml
EXPOSE 11434
CMD ["litellm", "--config", "/app/litellm_config.yaml", "--port", "11434", "--host", "0.0.0.0"]
