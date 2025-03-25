import celery
from django.core import management


@celery.shared_task
def clear_expired_sessions():
    management.call_command("clearsessions")
    print("Finished clearing expired sessions from DB")
