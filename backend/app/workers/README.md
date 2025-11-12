# Backend Workers

This directory contains the Celery workers and tasks for handling background processing.

## Running the Worker

To start the Celery worker, navigate to the project's root directory and run the following command:

```bash
celery -A backend.app.workers.celery_app worker --loglevel=info
```

Make sure your Redis server is running, as it's used as the message broker and backend for Celery. The connection settings are configured in `.env` at the project root.
