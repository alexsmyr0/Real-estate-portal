FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY manage.py pyproject.toml ./
COPY src ./src
COPY templates ./templates
COPY tests ./tests

RUN pip install --no-cache-dir --no-deps .

EXPOSE 8080

CMD ["python", "manage.py", "runserver", "0.0.0.0:8080"]
