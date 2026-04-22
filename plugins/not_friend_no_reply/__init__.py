from nonebot.message import run_preprocessor
from nonebot.exception import IgnoredException
from nonebot.internal.adapter import Event
from nonebot import Bot


@run_preprocessor
async def preprocessor(event: Event, bot: Bot):
    if hasattr(event, 'message_type') and event.message_type == "private" and event.sub_type != "friend":
        raise IgnoredException("not reply group temp message")
    if event.get_user_id() == bot.self_id:
        raise IgnoredException("ignore bot message")


