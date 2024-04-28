import re
import random

import unicodedata
import string

from nonebot import on_command
from nonebot.internal.adapter import Message
from nonebot.params import CommandArg
from nonebot.plugin import PluginMetadata
# from nonebot.adapters.red.message import MessageSegment as RedMessageSegment
# from nonebot.adapters.onebot.v11 import MessageEvent as v11MessageEvent

__plugin_meta__ = PluginMetadata(
    name='sayoroll',
    description='随机数字或随机事件',
    usage='roll[数字] / 事件1 事件2 .../ xxx要不要xxx',
    extra={}
)


roll = on_command(
    'roll',
    priority=1,
    block=False
)


def normalize_str(s):
    return unicodedata.normalize('NFKC', s)


@roll.handle()
async def _(args: Message = CommandArg()):
    args = str(args).strip()

    if not args:
        msg = '你的数字是[{}]'.format(random.randint(0, 100))
        await roll.finish(msg)

    elif args.isdigit():
        msg = '你的数字是[{}]'.format(random.randint(0, int(args)))
        await roll.finish(msg)

    args = normalize_str(args)
    args_without_punctuation = args.translate(str.maketrans('', '', string.punctuation))
    if re.search('^(.+)还是\\1$', args_without_punctuation):
        await roll.finish('总共就2个参数..还都相同..怎么roll都一样啊')

    elif re.search('^(.+)还是(.+)$', args):
        result = re.search('^(.+)还是(.+)$', args)
        options = [result.group(1), result.group(2)]
        msg = '当然是' + random.choice(options) + '咯'
        await roll.finish(Message(msg))

    if len(set(args_without_punctuation.split(' '))) == 1:
        msg = '总共就{}个参数..还都相同..怎么roll都一样啊'.format(len(args_without_punctuation.split(' ')))
        await roll.finish(msg)

    if any(args_without_punctuation.split(' ').count(x) >= 2 for x in set(args_without_punctuation.split(' '))):
        duplicate_options = [x for x in set(args_without_punctuation.split(' ')) if args_without_punctuation.split(' ').count(x) >= 2]
        msg = '[{}] 参数出现次数过多,想增大概率是吧'.format(','.join(duplicate_options))
        await roll.finish(msg)

    options = [x for x in args.split(' ') if x.strip()]
    if len(options) > 1 and not re.search('([\u4E00-\u9FA5]+)还是([\u4E00-\u9FA5]+)', args):
        msg = '当然是{}咯'.format(random.choice(options))
        await roll.finish(msg)

    elif re.search('([\u4E00-\u9FA5])([\u4E00-\u9FA5])\\1(.*?)', args) and not re.search('^([\u4E00-\u9FA5]+)还是([\u4E00-\u9FA5]+)$', args):
        result = re.search('([\u4E00-\u9FA5])([\u4E00-\u9FA5])\\1(.*?)', args)
        options = [result.group()[:1], result.group()[1:]]
        msg = '当然是' + args[:result.span()[0]].replace('我', '你').replace('你', '我') + random.choice(options) + args[result.span()[1]:]
        await roll.finish(msg)
    else:
        await roll.finish('未匹配到参数！')
