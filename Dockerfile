FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --uid 1000 --create-home --shell /usr/sbin/nologin appuser

COPY --chown=appuser:appuser . .
RUN mkdir -p /app/instance && chown -R appuser:appuser /app

USER appuser

EXPOSE 5000
CMD ["gunicorn", "-w", "1", "--threads", "4", "--timeout", "60", "-b", "0.0.0.0:5000", "run:app"]
