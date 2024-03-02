from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from django.conf import settings
import logging

# Set the default Django settings module for the Celery program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'credit_approval_system.settings')

# Initialize Celery app with appropriate configurations.
app = Celery('credit_approval_system')

# Load Django settings and configure Celery app.
try:
    app.config_from_object('django.conf:settings', namespace='CELERY')
except ImportError:
    logging.error("Unable to import Django settings module. Celery initialization failed.")
    raise

# Set task serializer, result serializer, and accepted content types.
app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    result_backend='redis://redis:6379/0',
)

# Disable UTC and set timezone.
app.conf.enable_utc = False
app.conf.update(timezone='Asia/Kolkata')

# Autodiscover tasks in all installed Django apps.
app.autodiscover_tasks()


# Define a debug task for testing Celery.
@app.task(bind=True)
def debug_task(self):
    logging.debug(f'Request: {self.request!r}')

if __name__ == '__main__':
    app.start()
