FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY backend /app/backend
COPY ml /app/ml
COPY sample_data /app/sample_data
COPY scripts/init_data.py /app/scripts/init_data.py
RUN mkdir -p /app/ml/artifacts /app/backend/uploads
EXPOSE 8000
CMD ["sh", "-c", "python scripts/init_data.py && uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"]
