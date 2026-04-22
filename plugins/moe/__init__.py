import random

import httpx
from nonebot import on_command, require, logger
require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import UniMessage


moe = on_command("moe", priority=11, block=True)
tx = on_command("头像", priority=11, block=True)
bg = on_command("bg", priority=11, block=True)

urls = ["https://vrandom-pic.acofork.us.kg", "https://www.loliapi.com/acg/pe/"]

url = random.choice(urls)


@moe.handle() 
async def _(): 
    try:
        # 1. 增加 timeout 超时限制 (比如 20 秒)，防止请求 API 一直卡死
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client: 
            data = await client.get("https://www.loliapi.com/acg/pe/") 
        
        # 2. 改用 .send() 发送，这样如果发送超时报错，会被下面的 except 捕获
        await UniMessage.image(raw=data.content).send()
        
    except Exception as e:
        # 3. 如果发生任何错误（API挂了、下载超时、OneBot发送超时等），就在这里拦截
        logger.error(f"moe指令发图失败，原因: {e}")
        # 给用户一个友好的提示（这步也是安全的，用 send）
        await UniMessage.text("网络开小差啦，图片发送超时或失败...").send()
        


@bg.handle()
async def _():
    async with httpx.AsyncClient(follow_redirects=True) as client:
        data = await client.get("https://www.loliapi.com/acg/pc/")
    await UniMessage.image(raw=data.content).finish()


@tx.handle()
async def _():
    await UniMessage.image(url="https://www.loliapi.com/acg/pp/").finish()
