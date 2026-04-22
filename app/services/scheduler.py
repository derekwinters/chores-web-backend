import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import delete

from ..database import AsyncSessionLocal
from ..models import ChoreLog
from .chore_service import transition_overdue_chores

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _midnight_transition() -> None:
    async with AsyncSessionLocal() as db:
        count = await transition_overdue_chores(db)
        if count:
            logger.info("Transitioned %d chore(s) to due", count)


async def _weekly_log_cleanup() -> None:
    from ..routers.log import _log_retention_days

    async with AsyncSessionLocal() as db:
        cutoff_date = datetime.now() - timedelta(days=_log_retention_days)
        result = await db.execute(delete(ChoreLog).where(ChoreLog.timestamp < cutoff_date))
        count = result.rowcount
        if count:
            logger.info("Deleted %d old log entry/entries", count)
        await db.commit()


def start_scheduler() -> None:
    scheduler.add_job(
        _midnight_transition,
        CronTrigger(hour=0, minute=0),
        id="midnight_transition",
        replace_existing=True,
    )
    scheduler.add_job(
        _weekly_log_cleanup,
        CronTrigger(day_of_week=6, hour=3, minute=0),
        id="weekly_log_cleanup",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)
