import asyncio
import random
import time
from io import BytesIO
from pathlib import Path

from nonebot.plugin import PluginMetadata, require
from nonebot import on_message, get_bot, Bot, on_command
from wordcloud import WordCloud

require('nonebot_plugin_tortoise_orm')
require('nonebot_plugin_session')
require('nonebot_plugin_alconna')

from nonebot.internal.adapter import Event, Message
from nonebot_plugin_tortoise_orm import add_model

from nonebot.exception import ActionFailed
from nonebot.params import Arg, CommandArg
from nonebot.rule import Rule
from nonebot.typing import T_State
from nonebot_plugin_session import EventSession
from nonebot_plugin_alconna import UniMessage

from .handler import LearningChat
from .models import ChatMessage, ChatAnswer
from .config import config_manager
from .logger import logger
from . import web_api, web_page

require('nonebot_plugin_apscheduler')
from nonebot_plugin_apscheduler import scheduler

NICKNAME = 'miyuki'
__plugin_meta__ = PluginMetadata(
    name='群聊学习',
    description='群聊学习',
    usage='群聊学习',
    extra={
        'author': '惜月',
        'priority': 16,
    }
)

add_model('plugins.repeat.models')
stop_words = ["的", "了", "是", "我", "你", "他", "她", "它", "我们", "你们", "他们", "边", "种", "只", "能", "用",
              "在", "有", "没有", "不是", "还是", "怎么", "这", "那", "这个", "那个", "这些", "那些", "下", "只",
              "就", "和", "与", "或", "以及", "及", "等", "等等", "感觉", "样", "之", "之一", "想", "啊", "人",
              "一", "二", "三", "四", "现", "会", "么", "什么", "点", "还", "没", "个", "不", "是", "为",
              "一些", "一种", "一会儿", "一样", "一起", "一直", "一般", "一部分", "一方面", "一点", "一次", "一定",
              "很", "非常", "特别", "更", "最", "太", "比较", "吗", "越", "好", "什", "喜欢", "然后", "应该", "知道",
              "可以", "能够", "可能", "也许", "也", "并且", "而且", "同时", "此外", "另外", "然而", "但是", "但",
              "因为", "所以", "由于", "即使", "尽管", "虽然", "不过", "只是", "而是", "因此", "所以", "行", "便",
              "如何", "怎样", "怎么样", "如", "例如", "比如", "像", "像是", "真", "们", "要"]


async def ChatRule(event: Event, state: T_State, bot: Bot, session: EventSession) -> bool:
    if answers := await LearningChat(event, bot, session).answer():
        state['answers'] = answers
        return True
    return False


learning_chat = on_message(priority=99, block=True, rule=Rule(ChatRule), state={
    'pm_name': '群聊学习',
    'pm_description': '(被动技能)bot会学习群友们的发言',
    'pm_usage': '群聊学习',
    'pm_priority': 1
})

frequency = on_command('词频')


@frequency.handle()
async def _(session: EventSession, arg: Message = CommandArg()):
    group = session.id2
    arg = arg.extract_plain_text().strip()
    if not arg:
        arg = '1'
    if not arg.isdigit():
        await frequency.finish('统计范围应为纯数字')
    ans = await ChatAnswer.filter(group_id=group, time__gte=int(time.time()) - 3600 * 24 * int(arg)).values_list(
        'keywords', flat=True)
    words = ' '.join(ans)
    for i in stop_words:
        words = words.replace(i, '')
    wc = WordCloud(font_path=str(Path(__file__).parent / "SourceHanSans.otf"), width=1000, height=500).generate(words).to_image()
    image_bytes = BytesIO()
    wc.save(image_bytes, format="PNG")
    await UniMessage.image(raw=image_bytes).send(reply_to=True)


@learning_chat.handle()
async def _(bot: Bot, event: Event, session: EventSession, answers=Arg('answers')):
    for answer in answers:
        try:
            logger.info(f'{NICKNAME}将向群{session.id2}回复"{answer}"')
            await learning_chat.send(answer)
            await ChatMessage.create(
                group_id=session.id2,
                user_id=bot.self_id,
                message_id=UniMessage.get_message_id(event, bot),
                message=answer,
                raw_message=answer,
                time=int(time.time()),
                plain_text=answer,
            )
            await asyncio.sleep(random.random() + 0.5)
        except ActionFailed:
            logger.info(f'{NICKNAME}向群{session.id2}<的回复<m>"{answer}"发送失败，可能处于风控中')

# @scheduler.scheduled_job('interval', minutes=3, misfire_grace_time=5)
# async def speak_up():
#     t1 = time.perf_counter()
#     if not config_manager.config.total_enable:
#         return
#     try:
#         bot = get_bot()
#     except ValueError:
#         return
#     if not (speak := await LearningChat.speak(int(bot.self_id))):
#         return
#     group_id, messages = speak
#     for msg in messages:
#         try:
#             logger.info(f'{NICKNAME}向群<m>{group_id}</m>主动发言<m>"{msg}"</m>')
#             await Text(msg).send_to(TargetQQGroup(group_id=group_id), bot)
#             await asyncio.sleep(random.randint(2, 4))
#         except ActionFailed:
#             logger.info(f'{NICKNAME}向群<m>{group_id}</m>主动发言<m>"{msg}"</m><r>发送失败，可能处于风控中</r>')
#     t2 = time.perf_counter()
#     logger.info(f'所用时间为{t2 - t1}s')
