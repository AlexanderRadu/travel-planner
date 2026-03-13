FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements/ /app/requirements/

RUN pip install --upgrade pip && \
    pip install -r requirements/prod.txt

COPY . /app/

EXPOSE 8000

WORKDIR /app/src


CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
