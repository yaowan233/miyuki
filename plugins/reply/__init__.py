from nonebot import on_message, require, Bot
from nonebot.internal.adapter import Event
from nonebot.params import Arg
from nonebot.typing import T_State
from nonebot.rule import Rule
from .reply import ReplyChat
import asyncio
import random

require('nonebot_plugin_userinfo')
from nonebot_plugin_userinfo import EventUserInfo, UserInfo, get_user_info


async def reply_rule(bot: Bot, event: Event, state: T_State) -> bool:
    if not event.is_tome():
        return False
    user_info = await get_user_info(bot, event, event.get_user_id())
    if answers := await ReplyChat(event, user_info).answer():
        state['answers'] = answers
        return True
    return False


chat_reply = on_message(priority=9999, block=True, rule=Rule(reply_rule))


@chat_reply.handle()
async def _(answers=Arg('answers')):
    for answer in answers:
        await chat_reply.send(answer)
        await asyncio.sleep(random.random() + 0.5)
