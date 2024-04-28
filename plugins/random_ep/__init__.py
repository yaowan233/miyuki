import os
import random
import httpx
from pathlib import Path
from nonebot import on_command, require
from nonebot.plugin import PluginMetadata
require('nonebot_plugin_alconna')
from nonebot_plugin_alconna import UniMessage
# from .nonebot_plugin_randomnana import *

dz = on_command('我测你们码', aliases={'随机丁真', '丁真', '一眼丁真'}, priority=50, block=True)
ikun = on_command("ikun", aliases={'小黑子', '坤坤', '随机坤坤'}, priority=50, block=True)
ht = on_command('随机胡桃', aliases={'胡桃', '七濑胡桃'}, priority=50, block=True)
cj = on_command('柴郡', aliases={'随机柴郡', '猫猫', '随机猫猫'}, priority=50, block=True)
kemomimi = on_command('kemomimi', aliases={'兽耳酱', '狐狸娘', '随机兽耳酱'}, priority=50, block=True)
bsn = on_command('白圣女', aliases={'随机白圣女'}, priority=50, block=True)


__plugin_meta__ = PluginMetadata(
    name="随机表情包",
    description="发送一张随机表情",
    usage="/白圣女\n/兽耳酱\n/柴郡\n/胡桃",
)


@dz.handle()
async def _():
    img_path = Path(os.path.join(os.path.dirname(__file__), "resource/dz"))
    all_file_name = os.listdir(str(img_path))
    img_name = random.choice(all_file_name)
    img = img_path / img_name
    with open(img, 'rb') as f:
        img = f.read()
    await UniMessage.image(raw=img).send()


@ikun.handle()
async def ikun_handle():
    async with httpx.AsyncClient() as client:
        r = await client.get('https://www.duxianmen.com/api/ikun/')
    await UniMessage.image(raw=r.content).send()


@ht.handle()
async def ikun_handle():
    async with httpx.AsyncClient() as client:
        r = await client.get('https://www.duxianmen.com/api/ht/')
    await UniMessage.image(raw=r.content).send()


@cj.handle()
async def _():
    img_path = Path(os.path.join(os.path.dirname(__file__), "resource/cj"))
    all_file_name = os.listdir(str(img_path))
    img_name = random.choice(all_file_name)
    img = img_path / img_name
    with open(img, 'rb') as f:
        img = f.read()
    await UniMessage.image(raw=img).send()


@kemomimi.handle()
async def _():
    async with httpx.AsyncClient() as client:
        r = await client.get('https://img.moehu.org/pic.php?id=kemomimi')
    await UniMessage.image(raw=r.content).send()


@bsn.handle()
async def _():
    img_path = Path(os.path.join(os.path.dirname(__file__), "resource/bsn"))
    all_file_name = os.listdir(str(img_path))
    img_name = random.choice(all_file_name)
    img = img_path / img_name
    with open(img, 'rb') as f:
        img = f.read()
    await UniMessage.image(raw=img).send()

# 建议使用 API 而不是本地
# 空间占用好大 >_<
