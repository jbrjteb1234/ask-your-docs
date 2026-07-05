FROM python:3.12-slim

WORKDIR /app

# Install deps first (with the vendored kit, which requirements.txt references)
# so this layer is cached across code-only changes.
COPY requirements.txt ./
COPY vendor ./vendor
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway injects PORT; default to 8000 for local `docker run`.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
