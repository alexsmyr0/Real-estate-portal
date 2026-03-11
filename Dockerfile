FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir .

EXPOSE 8080

CMD ["python", "-m", "homefinder"]
