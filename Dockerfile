FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY . .
RUN uv pip install --system --no-cache-dir .

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["fastapi", "run", "hazlo/main.py", "--port", "8000", "--host", "0.0.0.0"]
