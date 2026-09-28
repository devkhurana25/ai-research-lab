FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Runs schema creation against DATABASE_URL on boot (safe if tables already exist)
CMD sh -c "python -c 'from database.postgres_db import init_db; init_db()' && uvicorn api:app --host 0.0.0.0 --port 8000"
