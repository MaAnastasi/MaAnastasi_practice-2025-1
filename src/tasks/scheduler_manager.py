import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler


class SchedulerManager:
    def __init__(self, bot):
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self.bot = bot

    async def setup(self):
        self.scheduler.start()
        logging.info("Scheduler started with UTC timezone")

    async def add_task(self, user_id, task_text, due_date, job_id):
        try:
            self.scheduler.add_job(
                self.send_reminder,
                'date',
                run_date=due_date,
                args=(user_id, task_text),
                id=job_id,
                misfire_grace_time=300
            )
            logging.info(f"Task added: {job_id} for {due_date}")
        except Exception as e:
            logging.error(f"Error adding job: {e}")
            raise

    async def send_reminder(self, user_id, task_text):
        try:
            await self.bot.send_message(
                chat_id=user_id,
                text=f"⏰ Напоминание!\n{task_text}"
            )
            logging.info(f"Reminder sent to {user_id}")
        except Exception as e:
            logging.error(f"Error sending reminder: {e}")

    async def shutdown(self):
        self.scheduler.shutdown()

    async def remove_job(self, job_id: str):
        try:
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
                logging.info(f"Removed job: {job_id}")
        except Exception as e:
            logging.error(f"Error removing job {job_id}: {e}")
