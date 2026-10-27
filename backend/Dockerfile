FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && playwright install chromium
COPY backend/ /app/backend/
COPY sample_sites/ /app/sample_sites/
COPY frontend/dist/ /app/frontend/dist/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
