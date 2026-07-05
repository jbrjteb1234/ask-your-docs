FROM python:3.12-slim

WORKDIR /app

# Install deps first (with the vendored kit, which requirements.txt references)
# so this layer is cached across code-only changes.
COPY requirements.txt ./
COPY vendor ./vendor
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Answering model. Sonnet 5 ($3/$15 per Mtok) is ~60% the cost of Opus 4.8
# at strong quality for grounded Q&A. Override in Railway/.env to change.
ENV ANTHROPIC_MODEL=claude-sonnet-5

# Railway injects PORT; default to 8000 for local `docker run`.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
