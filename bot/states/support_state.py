from aiogram.fsm.state import State, StatesGroup


class SupportFSM(StatesGroup):
    waiting_new_body = State()
    waiting_message = State()
    waiting_order_id = State()
    waiting_staff_reply = State()
