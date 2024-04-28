from collections import defaultdict
from pathlib import Path
from difflib import SequenceMatcher
from nonebot.internal.adapter import Event
import csv
import random

from nonebot_plugin_userinfo import UserInfo

reply = defaultdict(list)
path = osufile = Path(__file__).parent / 'chat.csv'
with open(path, encoding='UTF-8-sig') as f:
    reply_data = csv.reader(f, delimiter=';')
    for i, j in reply_data:
        reply[i].append(j)


def find_match(text, dictionary, threshold=0.6):
    match_str = max(dictionary.keys(), key=lambda x: SequenceMatcher(None, text, x).ratio())
    match_score = SequenceMatcher(None, text, match_str).ratio()
    if match_score >= threshold:
        return match_str
    else:
        return None


class ReplyChat:
    def __init__(self, event: Event, user_info: UserInfo):
        self.msg = event.get_plaintext()
        if user_info is None:
            self.target = '你'
        else:
            self.target = user_info.user_displayname or user_info.user_name

    async def answer(self):
        if ans := reply.get(self.msg):
            reply_str: str = random.choice(ans)
            reply_str = reply_str.replace('{me}', 'miyuki').replace('{name}', self.target)
            reply_ls = reply_str.split('{segment}')
            return reply_ls
        if key := find_match(self.msg, reply):
            reply_str: str = random.choice(reply[key])
            reply_str = reply_str.replace('{me}', 'miyuki').replace('{name}', self.target)
            reply_ls = reply_str.split('{segment}')
            return reply_ls
        return []
