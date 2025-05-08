import os
import asyncio
from aiogram import Bot, Dispatcher
from config.config import load_config
from database import db
from routers.user_router import router as user_router
from tasks.scheduler_manager import SchedulerManager

async def wait_for_db(pool, max_retries=5, delay=5):
    for _ in range(max_retries):
        try:
            async with pool.acquire() as conn:
                await conn.execute("SELECT 1")
                return True
        except Exception:
            await asyncio.sleep(delay)
    raise Exception("Failed to connect to database")

async def main():
    config = load_config(os.path.join(os.path.dirname(__file__), 'config/config.env'))
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()
    
    pool = await db.create_pool()
    await wait_for_db(pool)
    await db.create_tables(pool)
    
    scheduler_manager = SchedulerManager(bot)
    await scheduler_manager.setup()
    
    dp.include_router(user_router)
    
    try:
        await dp.start_polling(bot, pool=pool, scheduler_manager=scheduler_manager)
    finally:
        await pool.close()
        await scheduler_manager.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
