"""
Scheduler Service
Automated crawl scheduling using APScheduler.
Runs crawls daily at 09:00 and 14:00 KST.

📅 크롤링 스케줄:
- 오전 9 시 (09:00 KST) = 00:00 UTC
- 오후 2 시 (14:00 KST) = 05:00 UTC

오전 9 시와 오후 2 시가 계속 반복되어 크롤링 스케줄 간에 교차 실행됩니다.
"""

import os
from datetime import datetime
from typing import Callable, Optional, Dict, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger


class CrawlScheduler:
    """
    Manages automated crawl scheduling.
    Real-time web crawling at 9 AM and 2 PM KST for both Apple and Samsung.
    
    Schedule:
    - 09:00 KST (00:00 UTC) - Morning crawl
    - 14:00 KST (05:00 UTC) - Afternoon crawl
    
    Both Apple.com and Samsung.com are crawled at each schedule.
    """

    def __init__(self, cron_expression: str = None):
        self.scheduler = AsyncIOScheduler()
        # 09:00 KST = 00:00 UTC, 14:00 KST = 05:00 UTC
        self.cron_expression = cron_expression or os.getenv("CRAWL_SCHEDULE", "0 0,5 * * *")
        self.is_running = False
        self.jobs: Dict[str, Any] = {}

    def add_crawl_job(
        self,
        job_id: str,
        crawl_func: Callable,
        site_name: str,
        cron_expression: str = None,
    ):
        """
        Add a crawl job to the scheduler.

        Args:
            job_id: Unique job identifier
            crawl_func: Async function to execute
            site_name: 'apple' or 'samsung'
            cron_expression: Optional custom cron expression
        """
        cron = cron_expression or self.cron_expression

        # Parse cron expression for APScheduler
        # Format: minute hour day month day_of_week
        parts = cron.split()
        if len(parts) == 5:
            minute, hour, day, month, day_of_week = parts
        else:
            # Default to twice daily
            minute, hour = "0", "0,5"
            day, month, day_of_week = "*", "*", "*"

        trigger = CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            timezone="Asia/Seoul",
        )

        self.scheduler.add_job(
            func=crawl_func,
            trigger=trigger,
            id=job_id,
            name=f"Crawl {site_name.capitalize()}.com",
            replace_existing=True,
            kwargs={"site_name": site_name},
        )

        self.jobs[job_id] = {
            "site_name": site_name,
            "cron_expression": cron,
            "next_run": None,
        }

        logger.info(f"Added crawl job '{job_id}' for {site_name}.com with schedule: {cron}")

    def start(self):
        """Start the scheduler"""
        if not self.is_running:
            self.scheduler.start()
            self.is_running = True
            logger.info("Crawl scheduler started")

    def shutdown(self, wait: bool = True):
        """Shutdown the scheduler"""
        if self.is_running:
            self.scheduler.shutdown(wait=wait)
            self.is_running = False
            logger.info("Crawl scheduler stopped")

    def pause_job(self, job_id: str):
        """Pause a specific job"""
        if job_id in self.jobs:
            self.scheduler.pause_job(job_id)
            logger.info(f"Paused job: {job_id}")

    def resume_job(self, job_id: str):
        """Resume a paused job"""
        if job_id in self.jobs:
            self.scheduler.resume_job(job_id)
            logger.info(f"Resumed job: {job_id}")

    def remove_job(self, job_id: str):
        """Remove a job from the scheduler"""
        if job_id in self.jobs:
            self.scheduler.remove_job(job_id)
            del self.jobs[job_id]
            logger.info(f"Removed job: {job_id}")

    def get_job_info(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific job"""
        job = self.scheduler.get_job(job_id)
        if job:
            return {
                "id": job.id,
                "name": job.name,
                "next_run_time": str(job.next_run_time) if job.next_run_time else None,
                "trigger": str(job.trigger),
            }
        return None

    def get_all_jobs(self) -> Dict[str, Any]:
        """Get information about all scheduled jobs"""
        jobs_info = {}
        for job in self.scheduler.get_jobs():
            jobs_info[job.id] = {
                "id": job.id,
                "name": job.name,
                "next_run_time": str(job.next_run_time) if job.next_run_time else None,
                "trigger": str(job.trigger),
            }
        return jobs_info

    def run_now(self, job_id: str):
        """Trigger a job to run immediately"""
        if job_id in self.jobs:
            job = self.scheduler.get_job(job_id)
            if job:
                job.modify(next_run_time=datetime.now())
                logger.info(f"Triggered immediate run for job: {job_id}")
                return True
        return False


# Global scheduler instance
scheduler = CrawlScheduler()


def get_scheduler() -> CrawlScheduler:
    """Get the global scheduler instance"""
    return scheduler


def init_scheduler(crawl_func: Callable, email_report_func: Callable = None):
    """
    Initialize scheduler with crawl function and email reports.
    
    📅 Real-time crawling schedule (KST):
    - Morning: 09:00 KST (00:00 UTC) - Apple & Samsung
    - Afternoon: 14:00 KST (05:00 UTC) - Apple & Samsung
    
    Both Apple.com and Samsung.com are crawled at each schedule time.
    The crawls fetch real-time web data, not snapshots.
    
    Args:
        crawl_func: The main crawl function to schedule
        email_report_func: Optional tuple of (morning_report_func, afternoon_report_func)
    """
    # === MORNING CRAWLS at 09:00 KST (00:00 UTC) ===
    # Apple morning crawl - real-time web crawling
    scheduler.add_crawl_job(
        job_id="apple_morning_crawl",
        crawl_func=crawl_func,
        site_name="apple",
        cron_expression="0 9 * * *",  # 09:00 KST
    )

    # Samsung morning crawl - real-time web crawling  
    scheduler.add_crawl_job(
        job_id="samsung_morning_crawl",
        crawl_func=crawl_func,
        site_name="samsung",
        cron_expression="0 9 * * *",  # 09:00 KST
    )

    # === AFTERNOON CRAWLS at 14:00 KST ===
    # Apple afternoon crawl - real-time web crawling
    scheduler.add_crawl_job(
        job_id="apple_afternoon_crawl",
        crawl_func=crawl_func,
        site_name="apple",
        cron_expression="0 14 * * *",  # 14:00 KST
    )

    # Samsung afternoon crawl - real-time web crawling
    scheduler.add_crawl_job(
        job_id="samsung_afternoon_crawl",
        crawl_func=crawl_func,
        site_name="samsung",
        cron_expression="0 14 * * *",  # 14:00 KST
    )

    # Add email report jobs if provided
    if email_report_func:
        morning_func, afternoon_func = email_report_func

        # Morning report 09:30 KST (크롤 완료 후 30분 뒤)
        scheduler.scheduler.add_job(
            func=morning_func,
            trigger=CronTrigger(hour=9, minute=30, timezone="Asia/Seoul"),
            id="morning_email_report",
            name="Morning Email Report",
            replace_existing=True,
        )

        # Afternoon report 14:30 KST (크롤 완료 후 30분 뒤)
        scheduler.scheduler.add_job(
            func=afternoon_func,
            trigger=CronTrigger(hour=14, minute=30, timezone="Asia/Seoul"),
            id="afternoon_email_report",
            name="Afternoon Email Report",
            replace_existing=True,
        )

        logger.info("Email report jobs added to scheduler")

    logger.info("📅 Scheduler initialized with real-time crawls at 09:00 and 14:00 KST for Apple and Samsung")
    return scheduler
