from nonebot.message import run_preprocessor
from nonebot.exception import IgnoredException
from nonebot.internal.adapter import Event
from nonebot import Bot
from nonebot.adapters.satori import MessageEvent
from nonebot.adapters.onebot.v11 import GroupMessageEvent as v11MessageEvent

white_list = ['730139506', '708115630', '247833096', '468606247', '931213301', '1020145437', '646960504', '729435957', '735113523', '673263142', '686681834', '238242668', '280079266', '719244813', '684532130', '555363998', '682415486']


@run_preprocessor
async def preprocessor(event: Event, bot: Bot):
    if hasattr(event, 'message_type') and event.message_type == "private" and event.sub_type != "friend":
        raise IgnoredException("not reply group temp message")
    if event.get_user_id() == bot.self_id:
        raise IgnoredException("ignore bot message")


