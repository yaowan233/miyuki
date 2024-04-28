import asyncio
import datetime
import random
import time
from collections import Counter
from functools import cmp_to_key

from nonebot.internal.adapter import Event
from nonebot_plugin_alconna import UniMessage
from nonebot_plugin_alconna.uniseg import reply_fetch
from nonebot_plugin_session import EventSession

try:
    import jieba_fast.analyse as jieba_analyse
except ImportError:
    import jieba.analyse as jieba_analyse
from typing import List, Union, Optional, Tuple
from enum import IntEnum, auto
from nonebot import get_bot, Bot
from tortoise.functions import Count
from .models import ChatBlackList, ChatContext, ChatAnswer, ChatMessage
from .config import config_manager, NICKNAME, COMMAND_START, log_info, log_debug

chat_config = config_manager.config

SORRY_WORDS = [f'{NICKNAME}知道错了...达咩!', f'{NICKNAME}不会再这么说了...', f'果面呐噻,{NICKNAME}说错话了...']
DOUBT_WORDS = [f'{NICKNAME}有说什么奇怪的话吗？']
BREAK_REPEAT_WORDS = ['打断复读', '打断！']
ALL_WORDS = SORRY_WORDS + DOUBT_WORDS + BREAK_REPEAT_WORDS


class Result(IntEnum):
    Learn = auto()
    Pass = auto()
    Repeat = auto()
    Ban = auto()
    SetEnable = auto()
    SetDisable = auto()


class LearningChat:
    def __init__(self, event: Event, bot: Bot, session: EventSession):
        self.bot = bot
        self.event = event
        self.data = ChatMessage(
            group_id=session.id2,
            user_id=session.id1,
            message_id=UniMessage.get_message_id(event, bot),
            message=event.get_plaintext().strip(),
            raw_message=event.get_plaintext(),
            plain_text=event.get_plaintext(),
            time=int(time.time())
        )
        self.bot_id = 1784933404
        self.to_me = event.is_tome() or NICKNAME in self.data.message
        self.role = 'superuser'
        self.config = config_manager.get_group_config(self.data.group_id)
        self.ban_users = set(chat_config.ban_users + self.config.ban_users)
        self.ban_words = set(chat_config.ban_words + self.config.ban_words)

    async def _learn(self) -> Result:
        if self.to_me and any(
                w in self.data.message for w in {'学说话', '快学', '开启学习'}):
            return Result.SetEnable
        elif self.to_me and any(
                w in self.data.message for w in {'闭嘴', '别学', '关闭学习'}):
            return Result.SetDisable
        elif not chat_config.total_enable or not self.config.enable:
            log_debug('群聊学习', f'➤该群<m>{self.data.group_id}</m>未开启群聊学习，跳过')
            # 如果未开启群聊学习，跳过
            return Result.Pass
        elif COMMAND_START and self.data.message.startswith(tuple(COMMAND_START)):
            # 以命令前缀开头的消息，跳过
            log_debug('群聊学习', '➤该消息以命令前缀开头，跳过')
            return Result.Pass
        elif self.data.user_id in self.ban_users:
            # 发言人在屏蔽列表中，跳过
            log_debug('群聊学习', f'➤发言人<m>{self.data.user_id}</m>在屏蔽列表中，跳过')
            return Result.Pass
        elif self.to_me and any(w in self.data.message for w in {'不可以', '达咩', '不能说这', '不许'}):
            # 如果是对某句话进行禁言
            return Result.Ban
        elif not self.data.message or not await self._check_allow(self.data):
            # 本消息不合法，跳过
            log_debug('群聊学习', '➤消息未通过校验，跳过')
            return Result.Pass
        elif reply := await reply_fetch(self.event, self.bot):
            # 如果是回复消息
            message_id = reply.id
            if not message_id or not message_id.isdigit():
                return Result.Pass
            if not (message := await ChatMessage.filter(message_id=message_id).first()):
                # 回复的消息在数据库中有记录
                log_debug('群聊学习', '➤回复的消息不在数据库中，跳过')
                return Result.Pass
            if message.user_id in self.ban_users:
                # 且回复的人不在屏蔽列表中
                log_debug('群聊学习', '➤回复的人在屏蔽列表中，跳过')
                return Result.Pass
            if not await self._check_allow(message):
                # 且回复的内容通过校验
                log_debug('群聊学习', '➤回复的消息未通过校验，跳过')
                return Result.Pass
            # 则将该回复作为该消息的答案
            await self._set_answer(message)
            return Result.Learn
        elif messages := await ChatMessage.filter(group_id=self.data.group_id, time__gte=self.data.time - 3600).limit(
                20):
            # 获取本群一个小时内的最后5条消息
            c = Counter([i.message for i in messages])
            if c[self.data.message] > 1:
                # 判断是否为复读中
                log_debug('群聊学习', '➤复读中，跳过')
                return Result.Repeat
            for message in messages:
                # 如果5条内有相关信息，就作为该消息的答案
                if message.user_id not in self.ban_users and set(self.data.keyword_list) & set(
                        message.keyword_list) and self.data.keyword_list != message.keyword_list and await self._check_allow(
                    message):
                    await self._set_answer(message)
                    return Result.Learn
            # 如果没有相关信息
            if messages[0].user_id in self.ban_users or not await self._check_allow(messages[0]):
                # 且最后一条消息的发送者不在屏蔽列表中并通过校验
                log_debug('群聊学习', '➤最后一条消息未通过校验，跳过')
                return Result.Pass
            # 则作为最后一条消息的答案
            await self._set_answer(messages[0])
            return Result.Learn
        else:
            # 不符合任何情况，跳过
            return Result.Pass

    async def answer(self) -> Optional[List[Union[str]]]:
        """获取这句话的回复"""
        result = await self._learn()
        await self.data.save()
        if result == Result.Ban:
            # 禁用某句话
            if self.role not in {'superuser', 'admin', 'owner'}:
                # 检查权限
                return None
            if reply := await reply_fetch(self.event, self.bot):
                ban_result = await self._ban(message_id=reply.id)
            else:
                ban_result = await self._ban()
            if ban_result:
                return [random.choice(SORRY_WORDS)]
            else:
                return [random.choice(DOUBT_WORDS)]
        # elif result in [Result.SetEnable, Result.SetDisable]:
        #     # 检查权限
        #     if self.role not in {'superuser', 'admin', 'owner'}:
        #         return [random.choice(NO_PERMISSION_WORDS)]
        #     self.config.update(enable=(result == Result.SetEnable))
        #     config_manager.config.group_config[self.data.group_id] = self.config
        #     config_manager.save()
        #     log_info('群聊学习',
        #              f'群<m>{self.data.group_id}</m>{"开启" if result == Result.SetEnable else "关闭"}学习功能')
        #     return [random.choice(ENABLE_WORDS if result == Result.SetEnable else DISABLE_WORDS)]
        elif result == Result.Pass:
            # 跳过
            return None
        elif result == Result.Repeat:
            if await ChatMessage.filter(group_id=self.data.group_id,
                                        time__gte=self.data.time - 3600)\
                    .limit(self.config.repeat_threshold + 20)\
                    .filter(user_id=self.bot_id, message=self.data.message).exists():
                # 如果在阈值+5条消息内，bot已经回复过这句话，则跳过
                log_debug('群聊学习', '➤➤已经复读过了，跳过')
                return None
            if not (messages := await ChatMessage.filter(
                    group_id=self.data.group_id,
                    time__gte=self.data.time - 3600).limit(20)):
                return None
            # 如果达到阈值，且不是全都为同一个人在说，则进行复读
            repeated_messages = [message for message in messages if message.message == self.data.message]
            if any(message.user_id != self.data.user_id for message in repeated_messages) and random.random() < 0.3:
                log_debug('群聊学习', f'➤➤复读<m>{messages[0].message}</m>')
                return [self.data.message]
            return None
        else:
            # 回复
            if self.data.is_plain_text and len(self.data.plain_text) <= 1:
                log_debug('群聊学习', '➤➤消息过短，不回复')
                return None
            if not (context := await ChatContext.filter(keywords=self.data.keywords).first()):
                log_debug('群聊学习', '➤➤尚未有已学习的回复，不回复')
                return None

            # 获取回复阈值
            if not self.to_me:
                answer_choices = list(
                    range(self.config.answer_threshold - len(self.config.answer_threshold_weights) + 1,
                          self.config.answer_threshold + 1))

                answer_count_threshold = random.choices(answer_choices, weights=self.config.answer_threshold_weights)[0]

                if len(self.data.keyword_list) == chat_config.KEYWORDS_SIZE:
                    answer_count_threshold -= 1
                cross_group_threshold = chat_config.cross_group_threshold
            else:
                answer_count_threshold = 1
                cross_group_threshold = 1
            log_debug('群聊学习',
                      f'➤➤本次回复阈值为<m>{answer_count_threshold}</m>，跨群阈值为<m>{cross_group_threshold}</m>')
            # 获取满足跨群条件的回复
            answers_cross = await ChatAnswer.filter(context=context, count__gte=answer_count_threshold).annotate(
                cross=Count('keywords')).group_by('keywords').filter(
                cross__gte=1)
            answer_same_group = await ChatAnswer.filter(context=context, count__gte=answer_count_threshold,
                                                        group_id=self.data.group_id)

            candidate_answers: List[Optional[ChatAnswer]] = []
            # 检查候选回复是否在屏蔽列表中
            for answer in set(answers_cross) | set(answer_same_group):
                if not await self._check_allow(answer):
                    continue
                # if answer_count_threshold > 0:
                #     answer.count -= answer_count_threshold - 1
                candidate_answers.append(answer)
            if not candidate_answers:
                log_debug('群聊学习', '➤➤没有符合条件的候选回复')
                return None

            # 从候选回复中进行选择
            sum_count = sum(answer.count for answer in candidate_answers)
            per_list = [answer.count / sum_count * (1 - 1 / answer.count) for answer in candidate_answers]

            per_list.append(1 - sum(per_list))
            answer_dict = tuple(zip(candidate_answers, per_list))
            log_debug('群聊学习',
                      f'➤➤候选回复有<m>{"|".join([f"""{a.keywords}({round(p, 3)})""" for a, p in answer_dict])}|不回复({round(per_list[-1], 3)})</m>')

            if (result := random.choices(candidate_answers + [None], weights=per_list)[0]) is None:
                log_debug('群聊学习', '➤➤但不进行回复')
                return None
            result_message = random.choice(result.messages)
            log_debug('群聊学习', f'➤➤将回复<m>{result_message}</m>')
            await asyncio.sleep(random.random() + 0.5)
            return [result_message]

    async def _ban(self, message_id: Optional[str] = None) -> bool:
        """屏蔽消息"""
        bot = get_bot()
        if message_id and message_id.isdigit():
            if not (message := await ChatMessage.filter(message_id=message_id).first()) or message.message in ALL_WORDS:
                return False
            keywords = message.keywords
            # try:
            #     await bot.delete_msg(message_id=message_id)
            # except ActionFailed:
            #     log_info('群聊学习', f'待禁用消息<m>{message_id}</m>尝试撤回<r>失败</r>')
        elif (last_reply := await ChatMessage.filter(group_id=self.data.group_id, user_id=self.bot_id).first()) and (
                last_reply.message not in ALL_WORDS):
            # 没有指定消息ID，则屏蔽最后一条回复
            keywords = last_reply.keywords
            # try:
            #     await bot.delete_msg(message_id=last_reply.message_id)
            # except ActionFailed:
            #     log_info('群聊学习', f'待禁用消息<m>{last_reply.message_id}</m>尝试撤回<r>失败</r>')
        else:
            return False
        if ban_word := await ChatBlackList.filter(keywords=keywords).first():
            # 如果已有屏蔽记录
            if self.data.group_id not in ban_word.ban_group_id:
                # 如果不在屏蔽群列表中，则添加
                ban_word.ban_group_id.append(self.data.group_id)
            if len(ban_word.ban_group_id) >= 8:
                # 如果有超过2个群都屏蔽了该条消息，则全局屏蔽
                ban_word.global_ban = True
                log_info('群聊学习', f'学习词<m>{keywords}</m>将被全局禁用')
                await ChatAnswer.filter(keywords=keywords).delete()
            else:
                log_info('群聊学习', f'群<m>{self.data.group_id}</m>禁用了学习词<m>{keywords}</m>')
                await ChatAnswer.filter(keywords=keywords, group_id=self.data.group_id).delete()
        else:
            # 没有屏蔽记录，则新建
            log_info('群聊学习', f'群<m>{self.data.group_id}</m>禁用了学习词<m>{keywords}</m>')
            ban_word = ChatBlackList(keywords=keywords, ban_group_id=[self.data.group_id])
            await ChatAnswer.filter(keywords=keywords, group_id=self.data.group_id).delete()
        await ChatContext.filter(keywords=keywords).delete()
        await ban_word.save()
        return True

    @staticmethod
    async def add_ban(data: Union[ChatMessage, ChatContext, ChatAnswer]):
        if ban_word := await ChatBlackList.filter(keywords=data.keywords).first():
            # 如果已有屏蔽记录
            if isinstance(data, ChatMessage):
                if data.group_id not in ban_word.ban_group_id:
                    # 如果不在屏蔽群列表中，则添加
                    ban_word.ban_group_id.append(data.group_id)
                if len(ban_word.ban_group_id) >= 2:
                    # 如果有超过2个群都屏蔽了该条消息，则全局屏蔽
                    ban_word.global_ban = True
                    log_info('群聊学习', f'学习词<m>{data.keywords}</m>将被全局禁用')
                    await ChatAnswer.filter(keywords=data.keywords).delete()
                else:
                    log_info('群聊学习', f'群<m>{data.group_id}</m>禁用了学习词<m>{data.keywords}</m>')
                    await ChatAnswer.filter(keywords=data.keywords, group_id=data.group_id).delete()
            else:
                ban_word.global_ban = True
                log_info('群聊学习', f'学习词<m>{data.keywords}</m>将被全局禁用')
                await ChatAnswer.filter(keywords=data.keywords).delete()
        else:
            # 没有屏蔽记录，则新建
            if isinstance(data, ChatMessage):
                log_info('群聊学习', f'群<m>{data.group_id}</m>禁用了学习词<m>{data.keywords}</m>')
                ban_word = ChatBlackList(keywords=data.keywords, ban_group_id=[data.group_id])
                await ChatAnswer.filter(keywords=data.keywords, group_id=data.group_id).delete()
            else:
                log_info('群聊学习', f'学习词<m>{data.keywords}</m>将被全局禁用')
                ban_word = ChatBlackList(keywords=data.keywords, global_ban=True)
                await ChatAnswer.filter(keywords=data.keywords).delete()
        await ChatContext.filter(keywords=data.keywords).delete()
        await ban_word.save()

    @staticmethod
    async def speak(self_id: int) -> Optional[Tuple[int, List[Union[str]]]]:
        # 主动发言
        cur_time = int(time.time())
        today_time = time.mktime(datetime.date.today().timetuple())
        # 获取两小时内消息超过10条的群列表
        groups = await ChatMessage.filter(time__gte=cur_time - 3600).annotate(count=Count('id')).group_by('group_id'). \
            filter(count__gte=10).values_list('group_id', flat=True)
        if not groups:
            return None
        total_messages = {}
        # 获取这些群的两小时内的所有消息
        for group_id in groups:
            if messages := await ChatMessage.filter(group_id=group_id, time__gte=today_time - 3600):
                total_messages[group_id] = messages
        if not total_messages:
            return None

        # 根据消息平均间隔来对群进行排序
        def group_popularity_cmp(left_group: Tuple[int, List[ChatMessage]],
                                 right_group: Tuple[int, List[ChatMessage]]):
            def cmp(a, b):
                return (a > b) - (a < b)

            left_group_id, left_messages = left_group
            right_group_id, right_messages = right_group
            left_duration = left_messages[0].time - left_messages[-1].time
            right_duration = right_messages[0].time - right_messages[-1].time
            return cmp(len(left_messages) / left_duration, len(right_messages) / right_duration)

        popularity: List[Tuple[int, List[ChatMessage]]] = sorted(total_messages.items(),
                                                                 key=cmp_to_key(group_popularity_cmp), reverse=True)
        log_debug('群聊学习', f'主动发言：群热度排行<m>{">>".join([str(g[0]) for g in popularity])}</m>')
        for group_id, messages in popularity:
            if len(messages) < 30:
                log_debug('群聊学习', f'主动发言：群<m>{group_id}</m>消息小于30条，不发言')
                continue

            config = config_manager.get_group_config(group_id)
            ban_words = set(
                chat_config.ban_words + config.ban_words + ['[CQ:xml', '[CQ:json', '[CQ:at', '[CQ:video', '[CQ:record',
                                                            '[CQ:share'])
            # 群里最后五条条消息为bot发言则不发言
            if any(self_id == message.user_id for message in messages[:5]):
                continue

            # 是否开启了主动发言
            if not config.speak_enable or not config.enable:
                log_debug('群聊学习', f'主动发言：群<m>{group_id}</m>未开启，不发言')
                continue

            # 如果最后一条消息是自己发的，则不主动发言
            if last_reply := await ChatMessage.filter(group_id=group_id, user_id=self_id).first():
                if last_reply.time >= messages[0].time:
                    log_debug('群聊学习',
                              f'主动发言：群<m>{group_id}</m>最后一条消息是{NICKNAME}发的{last_reply.message}，不发言')
                    continue
                elif cur_time - last_reply.time < config.speak_min_interval:
                    log_debug('群聊学习', f'主动发言：群<m>{group_id}</m>上次主动发言时间小于主动发言最小间隔，不发言')
                    continue

            # 该群每多少秒发一条消息
            avg_interval = (messages[0].time - messages[-1].time) / len(messages)
            # 如果该群已沉默的时间小于阈值，则不主动发言
            silent_time = cur_time - messages[0].time
            threshold = avg_interval * config.speak_threshold
            if silent_time < threshold:
                log_debug('群聊学习',
                          f'主动发言：群<m>{group_id}</m>已沉默时间({silent_time})小于阈值({int(threshold)})，不发言')
                continue
            speak_list = []
            if answers := await ChatAnswer.filter(group_id=group_id,
                                                  count__gte=3):
                random.shuffle(answers)
                answer = random.choices(answers,
                                        weights=[
                                            answer.count + 1 if answer.time >= today_time else answer.count
                                            for answer in answers])[0]
                message = random.choice(answer.messages)
                if len(message) < 2:
                    continue
                if message.startswith('&#91;') and message.endswith('&#93;'):
                    continue
                if any(word in message for word in ban_words):
                    continue
                speak_list.append(message)
                while random.random() < config.speak_continuously_probability and len(
                        speak_list) < config.speak_continuously_max_len:
                    if (follow_context := await ChatContext.filter(
                            keywords=answer.keywords).first()) and (
                            follow_answers := await ChatAnswer.filter(
                                group_id=group_id,
                                context=follow_context,
                                count__gte=config.answer_threshold)):
                        answer = random.choices(follow_answers,
                                                weights=[a.count + 1 if a.time >= today_time else a.count
                                                         for a in follow_answers])[0]
                        message = random.choice(answer.messages)
                        if len(message) < 2:
                            continue
                        if message.startswith('&#91;') and message.endswith('&#93;'):
                            continue
                        if message in speak_list:
                            continue
                        if all(word not in message for word in ban_words):
                            speak_list.append(message)
                    else:
                        break
                if speak_list:
                    # if random.random() < config.speak_poke_probability:
                    #     last_speak_users = {message.user_id for message in messages[:5] if message.user_id != self_id}
                    #     select_user = random.choice(list(last_speak_users))
                    #     speak_list.append(MessageSegment('poke', {'qq': select_user}))
                    return group_id, speak_list
                else:
                    log_debug('群聊学习', f'主动发言：群<m>{group_id}</m>没有找到符合条件的发言，不发言')
        log_debug('群聊学习', '主动发言：没有符合条件的群，不主动发言')
        return None

    async def _set_answer(self, message: ChatMessage):
        if context := await ChatContext.filter(keywords=message.keywords).first():
            if context.count < chat_config.learn_max_count:
                context.count += 1
            context.time = self.data.time
            if answer := await ChatAnswer.filter(keywords=self.data.keywords,
                                                 group_id=self.data.group_id,
                                                 context=context).first():
                if answer.count < chat_config.learn_max_count:
                    answer.count += 1
                answer.time = self.data.time
                if self.data.message not in answer.messages:
                    answer.messages.append(self.data.message)
            else:
                answer = ChatAnswer(keywords=self.data.keywords,
                                    group_id=self.data.group_id,
                                    time=self.data.time,
                                    context=context,
                                    messages=[self.data.message])
            await answer.save()
            await context.save()
        else:
            context = await ChatContext.create(keywords=message.keywords,
                                               time=self.data.time)
            answer = await ChatAnswer.create(keywords=self.data.keywords,
                                             group_id=self.data.group_id,
                                             time=self.data.time,
                                             context=context,
                                             messages=[self.data.message])
        log_debug('群聊学习', f'➤将被学习为<m>{message.message}</m>的回答，已学次数为<m>{answer.count}</m>')

    async def _check_allow(self, message: Union[ChatMessage, ChatAnswer]) -> bool:
        raw_message = message.message if isinstance(message, ChatMessage) else message.messages[0]
        # if len(raw_message) < 2:
        #     return False
        if any(i in raw_message for i in
               {'[CQ:xml', '[CQ:json', '[CQ:at', '[CQ:video', '[CQ:record', '[CQ:share'}):
            return False
        if any(i in raw_message for i in self.ban_words):
            return False
        if raw_message.startswith('&#91;') and raw_message.endswith('&#93;'):
            return False
        if ban_word := await ChatBlackList.filter(keywords=message.keywords).first():
            if ban_word.global_ban or message.group_id in ban_word.ban_group_id:
                return False
        return True
