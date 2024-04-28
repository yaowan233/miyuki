from nonebot import on_command
import random
import datetime
import hashlib


from nonebot.plugin import PluginMetadata
from nonebot.internal.adapter import Event

__plugin_meta__ = PluginMetadata(
    name="运势",
    description="查询运势",
    usage="/运势"
)


__plugin_name__ = '运势'
__plugin_usage__ = r"""
运势查询

/运势
"""


luck = on_command("luck", aliases={'运势', '运气'}, priority=6, block=True)


@luck.handle()
async def handle_first_receive(event: Event):
    user_id = event.get_user_id()
    random_seed_str = str([user_id, datetime.date.today()])
    md5 = hashlib.md5()
    md5.update(random_seed_str.encode('utf-8'))
    seed = md5.hexdigest()
    random.seed(seed)
    luck_point = random.randint(0, 100)
    s = "今日运势是--"
    if luck_point == 0:
        sentence = s + "大凶\n >_< 今天运气衰爆了"
        await luck.finish(sentence)
    elif luck_point <= 20:
        sentence = s + "小凶\n>_< 今天运气有点背"
        await luck.finish(sentence)
    elif luck_point <= 80:
        sentence = s + "小吉\n今天也要加油哦"
        await luck.finish(sentence)
    elif luck_point <= 99:
        sentence = s + "中吉\n今天运气不错，说不定有好事要发生？"
        await luck.finish(sentence)
    elif luck_point == 100:
        sentence = s + "大吉\n今天运气特别好！"
        await luck.finish(sentence)
