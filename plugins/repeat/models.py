import functools
from functools import cached_property
from typing import List

try:
    import ujson as json
except ImportError:
    import json
try:
    import jieba_fast as jieba
    import jieba_fast.analyse as jieba_analyse
except ImportError:
    import jieba
    import jieba.analyse as jieba_analyse
from tortoise import fields
from tortoise.models import Model
from .config import config_manager

config = config_manager.config

JSON_DUMPS = functools.partial(json.dumps, ensure_ascii=False)
jieba.setLogLevel(jieba.logging.INFO)


class ChatMessage(Model):
    id: int = fields.IntField(pk=True, generated=True, auto_increment=True)
    """自增主键"""
    group_id: str = fields.TextField()
    """群id"""
    user_id: str = fields.TextField()
    """用户id"""
    message_id: str = fields.TextField()
    """消息id"""
    message: str = fields.TextField()
    """消息"""
    raw_message: str = fields.TextField()
    """原始消息"""
    plain_text: str = fields.TextField()
    """纯文本消息"""
    time: int = fields.IntField()
    """时间戳"""

    class Meta:
        table = 'message'
        indexes = ('group_id', 'time')
        ordering = ['-time']

    @cached_property
    def is_plain_text(self) -> bool:
        """是否纯文本"""
        return '[CQ:' not in self.message

    @cached_property
    def keyword_list(self) -> List[str]:
        """获取纯文本部分的关键词列表"""
        if not self.is_plain_text and not len(self.plain_text):
            return []
        return jieba_analyse.extract_tags(self.plain_text, topK=config.KEYWORDS_SIZE)

    @cached_property
    def keywords(self) -> str:
        """获取纯文本部分的关键词结果"""
        if not self.is_plain_text and not len(self.plain_text):
            return self.message
        return self.message if len(self.keyword_list) < 2 else ' '.join(self.keyword_list)


class ChatContext(Model):
    id: int = fields.IntField(pk=True, generated=True, auto_increment=True)
    """自增主键"""
    keywords: str = fields.TextField()
    """关键词"""
    time: int = fields.IntField()
    """时间戳"""
    count: int = fields.IntField(default=1)
    """次数"""
    answers: fields.ReverseRelation['ChatAnswer']
    """答案"""

    class Meta:
        table = 'context'
        indexes = ('keywords', 'time')
        ordering = ['-time']


class ChatAnswer(Model):
    id: int = fields.IntField(pk=True, generated=True, auto_increment=True)
    """自增主键"""
    keywords: str = fields.TextField()
    """关键词"""
    group_id: str = fields.TextField()
    """群id"""
    count: int = fields.IntField(default=1)
    """次数"""
    time: int = fields.IntField()
    """时间戳"""
    messages: List[str] = fields.JSONField(encoder=JSON_DUMPS, default=list)
    """消息列表"""

    context: fields.ForeignKeyNullableRelation[ChatContext] = fields.ForeignKeyField(
        'default.ChatContext', related_name='answers', null=True)

    class Meta:
        table = 'answer'
        indexes = ('keywords', 'time')
        ordering = ['-time']


class ChatBlackList(Model):
    id: int = fields.IntField(pk=True, generated=True, auto_increment=True)
    """自增主键"""
    keywords: str = fields.TextField()
    """关键词"""
    global_ban: bool = fields.BooleanField(default=False)
    """是否全局禁用"""
    ban_group_id: List[str] = fields.JSONField(default=list)
    """禁用的群id"""

    class Meta:
        table = 'blacklist'
        indexes = ('keywords',)
