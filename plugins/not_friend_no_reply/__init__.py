from nonebot.message import run_preprocessor
from nonebot.exception import IgnoredException


@run_preprocessor
async def preprocessor(event):
    if hasattr(event, 'message_type') and event.message_type == "private" and event.sub_type != "friend":
        raise IgnoredException("not reply group temp message")
