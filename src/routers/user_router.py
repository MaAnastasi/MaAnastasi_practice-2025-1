import asyncpg
import logging
import pytz
import uuid
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from states.user_states import FSMTask
from database import db
from tasks.scheduler_manager import SchedulerManager
from datetime import datetime

router = Router()


def get_confirm_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить",
                                     callback_data="confirm"),
                InlineKeyboardButton(text="❌ Отменить", callback_data="cancel")
            ]
        ]
    )
    return keyboard


def get_task_keyboard(task_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Выполнено",
                    callback_data=f"complete_{task_id}"
                )
            ]
        ]
    )


@router.message(F.text == "/start")
async def start(message: Message):
    await message.answer(
        "Добро пожаловать! Используйте команды:\n"
        "/add_task - Добавить задачу\n"
        "/my_tasks - Мои активные задачи\n"
        "/completed_tasks - Выполненные задачи"
    )


@router.message(F.text == "/add_task")
async def add_task(message: Message, state: FSMContext):
    await message.answer("Введите описание задачи:")
    await state.set_state(FSMTask.enter_task_text)


@router.message(FSMTask.enter_task_text)
async def process_task_text(message: Message, state: FSMContext):
    await state.update_data(task_text=message.text)
    await message.answer("Введите дату и время в формате ДД.ММ.ГГГГ ЧЧ:ММ")
    await state.set_state(FSMTask.enter_due_date)


@router.message(FSMTask.enter_due_date)
async def process_due_date(
    message: Message,
    state: FSMContext,
    pool: asyncpg.Pool,
    scheduler_manager: SchedulerManager
):
    try:
        moscow_tz = pytz.timezone('Europe/Moscow')
        # Парсим с учетом московского времени
        naive_due_date = datetime.strptime(message.text, "%d.%m.%Y %H:%M")
        due_date = moscow_tz.localize(naive_due_date).astimezone(pytz.UTC)
    except ValueError:
        await message.answer("❌ Неверный формат даты! Попробуйте снова:")
        return

    data = await state.get_data()
    await state.clear()

    job_id = f"task_{message.from_user.id}_{uuid.uuid4()}"

    try:
        await scheduler_manager.add_task(
            user_id=message.from_user.id,
            task_text=data['task_text'],
            due_date=due_date,
            job_id=job_id
        )

        await db.add_task_to_db(
            pool=pool,
            user_id=message.from_user.id,
            task_text=data['task_text'],
            due_date=due_date,  # передаем datetime объект напрямую
            job_id=job_id
        )

        await message.answer(
            f"✅ Задача добавлена!\n"
            f"📝 Описание: {data['task_text']}\n"
            f"⏰ Дата: {due_date.astimezone(moscow_tz).strftime('%d.%m.%Y %H:%M')}",
            reply_markup=get_confirm_keyboard()
        )

    except Exception as e:
        logging.error(f"Error adding task: {e}")
        await message.answer("❌ Ошибка при добавлении задачи!")


@router.message(F.text == "/my_tasks")
async def show_tasks(message: Message, pool: asyncpg.Pool):
    tasks = await db.get_active_user_tasks(pool, message.from_user.id)
    if not tasks:
        await message.answer("У вас нет активных задач!")
        return

    response = ["Ваши активные задачи:"]
    for task in tasks:
        task_msg = (
            f"📌 {task['task_text']}\n"
            f"⏰ {task['due_date'].astimezone(pytz.timezone('Europe/Moscow')).strftime('%d.%m.%Y %H:%M')}\n"
            f"ID: {task['id']}"
        )
        await message.answer(
            task_msg,
            reply_markup=get_task_keyboard(task['id'])
        )

    await message.answer("ℹ️ Вы можете отметить задачу выполненной, используя кнопку ниже")


@router.callback_query(F.data.startswith("complete_"))
async def complete_task(
    callback: CallbackQuery,
    pool: asyncpg.Pool,
    scheduler_manager: SchedulerManager
):
    task_id = int(callback.data.split("_")[1])
    task = await db.get_task_by_id(pool, task_id)

    if not task:
        await callback.answer("Задача не найдена!")
        return

    if task['is_completed']:
        await callback.answer("Задача уже выполнена!")
        return

    try:
        # Помечаем задачу выполненной
        await db.mark_task_completed(pool, task_id)

        # Удаляем задание из scheduler
        if task['job_id']:
            await scheduler_manager.remove_job(task['job_id'])

        await callback.message.edit_text(
            text=f"✅ Задача выполнена!\n{callback.message.text}",
            reply_markup=None
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"Error completing task: {e}")
        await callback.answer("❌ Ошибка при обновлении задачи!")


@router.callback_query(F.data == "confirm")
async def confirm_task(callback: CallbackQuery):
    await callback.message.edit_text("✅ Задача подтверждена!")


@router.callback_query(F.data == "cancel")
async def cancel_task(
    callback: CallbackQuery,
    pool: asyncpg.Pool,
    scheduler_manager: SchedulerManager
):
    task_id = int(callback.message.text.split("ID: ")[-1])
    task = await db.get_task_by_id(pool, task_id)

    if task:
        await db.delete_task(pool, task_id)
        await scheduler_manager.remove_job(task['job_id'])
        await callback.message.edit_text("❌ Задача удалена!")
    else:
        await callback.answer("Задача не найдена!")


@router.message(F.text == "/completed_tasks")
async def show_completed_tasks(message: Message, pool: asyncpg.Pool):
    tasks = await db.get_completed_user_tasks(pool, message.from_user.id)
    if not tasks:
        await message.answer("У вас нет выполненных задач!")
        return

    response = ["Ваши выполненные задачи:"]
    for task in tasks:
        response.append(
            f"✅ {task['task_text']}\n"
            f"⏰ {task['due_date'].astimezone(pytz.timezone('Europe/Moscow')).strftime('%d.%m.%Y %H:%M')}\n"
            f"ID: {task['id']}"
        )

    await message.answer("\n\n".join(response))
