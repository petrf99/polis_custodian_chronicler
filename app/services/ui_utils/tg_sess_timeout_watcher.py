from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
import asyncio

# Session time out
async def start_timeout_watcher(
    state: FSMContext,
    target_state: State,
    timeout_seconds: int,
    callback_message: types.Message,
    start_kb
):
    await asyncio.sleep(timeout_seconds)
    current = await state.get_state()
    if current == target_state.state:
        await state.clear()
        await callback_message.answer(
            "⏳ Session expired due to inactivity.\nPlease start again.",
            reply_markup=start_kb
            )


