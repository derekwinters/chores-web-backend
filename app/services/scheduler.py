import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import delete

from ..database import AsyncSessionLocal
from ..models import ChoreLog
from .chore_service import transition_overdue_chores
from .update_check_service import check_for_updates

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


async def _periodic_update_check() -> None:
    """Periodic background task to check for app updates."""
    async with AsyncSessionLocal() as db:
        await check_for_updates(db)
        logger.debug("Update check completed")


def reschedule_transition(hour: int, tz: str) -> None:
    """Reschedule the overdue-chore transition job to run at the given hour in the given timezone."""
    scheduler.add_job(
        _midnight_transition,
        CronTrigger(hour=hour, minute=0, timezone=tz),
        id="midnight_transition",
        replace_existing=True,
    )
    logger.info("Rescheduled midnight_transition to %02d:00 %s", hour, tz)


def start_scheduler(due_hour: int = 6, timezone: str = "UTC") -> None:
    scheduler.add_job(
        _midnight_transition,
        CronTrigger(hour=due_hour, minute=0, timezone=timezone),
        id="midnight_transition",
        replace_existing=True,
    )
    scheduler.add_job(
        _weekly_log_cleanup,
        CronTrigger(day_of_week=6, hour=3, minute=0),
        id="weekly_log_cleanup",
        replace_existing=True,
    )
    scheduler.add_job(
        _periodic_update_check,
        IntervalTrigger(hours=24),
        id="periodic_update_check",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started (due_hour=%d, timezone=%s)", due_hour, timezone)


def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)
