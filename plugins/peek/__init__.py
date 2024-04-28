import nonebot

from fastapi import FastAPI, UploadFile, File
from expiringdict import ExpiringDict
from nonebot import on_command, require
from nonebot.plugin import PluginMetadata
require('nonebot_plugin_alconna')
from nonebot_plugin_alconna import UniMessage


app: FastAPI = nonebot.get_app()
pic = ExpiringDict(1, 300)
peek = on_command('peek')

__plugin_meta__ = PluginMetadata(
    name="peek",
    description="看一些不该看的东西（",
    usage="/peek"
)
@app.post("/pic/")
async def give_pic(file: UploadFile = File()):
    pic['pic'] = await file.read()
    return {"file": len(pic['pic'])}


@peek.handle()
async def _():
    f = pic.get('pic')
    if not f:
        await peek.finish('作者没有开电脑哦>_<')
    await UniMessage.image(raw=pic['pic']).send()
