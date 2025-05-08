import asyncpg
import os


async def create_pool():
    return await asyncpg.create_pool(
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
        database=os.getenv('POSTGRES_DB'),
        host=os.getenv('POSTGRES_HOST'),
        port=int(os.getenv('POSTGRES_PORT', 5432))
    )


async def create_tables(pool):
    async with pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_tasks(
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                task_text TEXT,
                due_date TIMESTAMP,
                job_id TEXT,
                is_completed BOOLEAN DEFAULT FALSE
            )
        ''')


async def add_task_to_db(pool, user_id, task_text, due_date, job_id):
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO user_tasks(user_id, task_text, due_date, job_id)
            VALUES($1, $2, $3::TIMESTAMP WITH TIME ZONE, $4)
        ''', user_id, task_text, due_date, job_id)


async def get_user_tasks(pool, user_id):
    async with pool.acquire() as conn:
        return await conn.fetch(
            'SELECT * FROM user_tasks WHERE user_id = $1 ORDER BY due_date',
            user_id
        )


async def get_completed_user_tasks(pool: asyncpg.Pool, user_id: int):
    async with pool.acquire() as conn:
        return await conn.fetch(
            '''SELECT * FROM user_tasks 
               WHERE user_id = $1 AND is_completed = TRUE 
               ORDER BY due_date DESC''',
            user_id
        )


async def delete_task(pool, task_id):
    async with pool.acquire() as conn:
        await conn.execute('DELETE FROM user_tasks WHERE id = $1', task_id)


async def get_task_by_id(pool: asyncpg.Pool, task_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            'SELECT * FROM user_tasks WHERE id = $1',
            task_id
        )


async def mark_task_completed(pool: asyncpg.Pool, task_id: int):
    async with pool.acquire() as conn:
        await conn.execute('''
            UPDATE user_tasks 
            SET is_completed = TRUE 
            WHERE id = $1
        ''', task_id)


async def get_active_user_tasks(pool: asyncpg.Pool, user_id: int):
    async with pool.acquire() as conn:
        return await conn.fetch(
            '''SELECT * FROM user_tasks 
               WHERE user_id = $1 AND is_completed = FALSE 
               ORDER BY due_date''',
            user_id
        )
