import datetime
import random
from typing import List

from nonebot import on_command, require
from nonebot.adapters.onebot.v11 import MessageSegment, Message, Bot, GroupMessageEvent
from nonebot.typing import T_State

from .main import get_related_maps, get_related_map
from .country_rank import get_score_list
from .models import NewScore, Beatmap
from .osu_network import osu_api

require("nonebot_plugin_htmlrender")
require('nonebot_plugin_alconna')
from nonebot_plugin_htmlrender import md_to_pic
from nonebot_plugin_alconna import UniMessage
from .utils import split_msg

ctb_recommend = on_command("ctb推荐", priority=11, block=True)
NGM = {"0": "osu", "1": "taiko", "2": "fruits", "3": "mania"}


@ctb_recommend.handle(parameterless=[split_msg()])
async def _(state: T_State, bot: Bot, event: GroupMessageEvent):
    if "error" in state:
        await UniMessage.text(state["error"]).finish(reply_to=True)
    user = state["user"]
    mods = state["mods"]
    maps = await get_related_maps(user, "".join(mods))
    if len(maps) > 99:
        maps = random.sample(maps, 99)
        maps.sort(key=lambda x: x[2], reverse=True)
    messages = [MessageSegment.node_custom(
            user_id=1784933404, nickname="ctb推荐", content=Message(f"{state['username']} pp推荐\n请自行筛选挑选符合自己pp吃分范围的图\n刷图容易值越大说明在相同pp下越容易进入自己的bp")
        )]
    for i in maps:
        text = f"https://osu.ppy.sh/b/{i[0]}\n"
        if i[1]:
            text += f"mods: {i[1]}\n"
        text += f"pp: {i[2]}\n"
        text += f"同pp下刷图容易值:{i[3]:.2f}"
        messages.append(MessageSegment.node_custom(
            user_id=1784933404, nickname="ctb推荐", content=Message(MessageSegment.text(text))
        ))
    res_id = await bot.call_api("send_forward_msg", messages=Message(messages), group_id=event.group_id)
    await bot.send_group_msg(group_id=event.group_id, message=Message(MessageSegment.forward(res_id)))


relative_recommend = on_command("相关图推荐", priority=11, block=True)


@relative_recommend.handle(parameterless=[split_msg()])
async def _(state: T_State):
    para = state["para"]
    mods = state["mods"]
    if not para.isdigit():
        await UniMessage.text("参数错误").finish(reply_to=True)
    maps = await get_related_map(int(para), "".join(mods))
    if not maps:
        await UniMessage.text("未找到相关图").finish(reply_to=True)
    raw_msg = f"<message>{state['username']} 相关图推荐</message>"
    for i in maps:
        text = f"https://osu.ppy.sh/b/{i[0]}\n"
        if i[1]:
            text += f"mods: {i[1]}\n"
        text += f"相关值:{i[2]:.2f}"
        raw_msg += f"<message>{text}</message>"
    msg = MessageSegment.raw(f"<message forward>{raw_msg}</message>")
    await relative_recommend.finish(msg)


global_rank = on_command('全球排名', priority=11, block=True)
country_rank = on_command('地区排名', priority=11, block=True)


@global_rank.handle(parameterless=[split_msg()])
async def _(state: T_State):
    scores = await get_score_list(state['para'], NGM[state["mode"]], state["mods"], False)
    if not scores:
        await UniMessage.text("暂无成绩").finish()
    map_info = await osu_api("map", mode=NGM[state["mode"]], map_id=state['para'])
    map_info = Beatmap(**map_info)
    pic = await render_pic(scores, map_info)
    await UniMessage.image(raw=pic).finish()


@country_rank.handle(parameterless=[split_msg()])
async def _(state: T_State):
    scores = await get_score_list(state['para'], NGM[state["mode"]], state["mods"], True)
    if not scores:
        await UniMessage.text("暂无成绩").finish()
    map_info = await osu_api("map", mode=NGM[state["mode"]], map_id=state['para'])
    map_info = Beatmap(**map_info)
    pic = await render_pic(scores, map_info)
    await UniMessage.image(raw=pic).finish()


async def render_pic(scores: List[NewScore], map_info: Beatmap):
    md = f"### {map_info.beatmapset.title} [{map_info.version}]\n⭐{map_info.difficulty_rating:.2f}\n\n"
    md += """| 排名 |      | 得分 | 准确率 | 玩家 | 最大连击 | Fruits | DRP MISS | MISS | PP   | 达成时间 | 模组 |
| ---- | ---- | ---- | ------ | ---- | -------- | ------ | -------- | ---- | ---- | -------- | ---- |"""
    for rank, score in enumerate(scores):
        mods = [i.acronym for i in score.mods if i.acronym != "CL"]
        play_time = datetime.datetime.strptime(score.ended_at, "%Y-%m-%dT%H:%M:%SZ") + datetime.timedelta(hours=8)
        now = datetime.datetime.now()
        time_delta = now - play_time
        if time_delta.days > 365:
            day = f"{time_delta.days // 365} 年前"
        elif time_delta.days > 30:
            day = f"{time_delta.days // 30} 月前"
        elif time_delta.days >= 1:
            day = f"{time_delta.days} 天前"
        elif time_delta.seconds >= 3600:
            day = f"{time_delta.seconds // 3600} 小时前"
        elif time_delta.seconds >= 60:
            day = f"{time_delta.seconds // 60} 分钟前"
        else:
            day = "刚刚"
        md += f"\n| {rank + 1} | {score.rank} | {score.legacy_total_score} | {(score.accuracy * 100):.1f}% | {score.user.username} | {score.max_combo} | {score.statistics.great or 0} | {score.statistics.small_tick_miss or 0} | {score.statistics.miss or 0} | {score.pp:.0f} | {day} | {' '.join(mods)} |"
    return await md_to_pic(md, width=1100)
