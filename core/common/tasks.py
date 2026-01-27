from celery import shared_task

@shared_task(name="core.common.tasks.ping_task")
def ping_task() -> str:
    return "pong"
