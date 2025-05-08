from aiogram.fsm.state import StatesGroup, State

class FSMTask(StatesGroup):
    enter_task_text = State()
    enter_due_date = State()
