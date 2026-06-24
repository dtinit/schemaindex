FROM python:3.11-slim

ENV APP_HOME /app
WORKDIR $APP_HOME

# Removes output stream buffering, allowing for more efficient logging
ENV PYTHONUNBUFFERED 1

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy local code to the container image.
COPY . .

CMD exec gunicorn --capture-output --bind 0.0.0.0:$PORT --workers 1 -k uvicorn.workers.UvicornWorker --timeout 0 schemaindex.asgi:application
