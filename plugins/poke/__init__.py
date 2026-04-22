import random
from nonebot import on_message, on_notice
from nonebot.rule import Rule
from nonebot.adapters.satori.event import MessageCreatedEvent
from nonebot.adapters.satori import MessageSegment
from nonebot.adapters.onebot.v11 import PokeNotifyEvent as v11PokeNotifyEvent, MessageSegment as v11MessageSegment, Bot


async def custom_rule(event: MessageCreatedEvent) -> bool:
    if event.original_message and event.original_message[0].type == "chronocat:poke" and event.original_message[0].data['userId'] == event.self_id:
        return True
    return False


handler = on_message(priority=99, block=True, rule=Rule(custom_rule))


@handler.handle()
async def _(event: MessageCreatedEvent):
    await handler.finish((MessageSegment("chronocat:poke", {"user-id": event.original_message[0].data["operatorId"]})))


async def poke_rule(event: v11PokeNotifyEvent) -> bool:
    if event.target_id == event.self_id:
        return True
    return False

v11poke = on_notice(priority=99, block=True, rule=Rule(poke_rule))

message_list = [
    ("MISS", 0.2),
    ("GOOD", 0.2),
    ("GREAT", 0.5),
    ("PERFECT", 0.4),
    ("CRITICAL PERFECT", 0.2)
]


@v11poke.handle()
async def _(event: v11PokeNotifyEvent, bot: Bot):
    await bot.group_poke(group_id=event.group_id, user_id=event.user_id)
    # await v11poke.finish(v11MessageSegment.poke('poke', event.get_user_id()))
