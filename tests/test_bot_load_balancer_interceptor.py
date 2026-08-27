import asyncio
import importlib
import unittest
from unittest.mock import patch

import nonebot

nonebot.init()

interceptor_module = importlib.import_module(
    "plugins.nonebot_plugin_bot_load_balancer.interceptor"
)
ScopedConfig = importlib.import_module(
    "plugins.nonebot_plugin_bot_load_balancer.config"
).ScopedConfig


class FakeBot:
    def __init__(self, self_id: str, handled_by: list[str], sent_by: list[str]):
        self.self_id = self_id
        self._handled_by = handled_by
        self._sent_by = sent_by

    async def handle_event(self, event):
        self._handled_by.append(self.self_id)
        if not hasattr(event, "group_id"):
            await self.call_api(
                "send_private_msg",
                user_id=event.get_user_id(),
                message="reply",
            )

    async def send(self, event, message, **kwargs):
        return None

    async def call_api(self, api: str, **data):
        self._sent_by.append(self.self_id)
        return None


class FakeBalancer:
    async def select_bot(self, session_id, candidate_bots, sticky):
        return candidate_bots["1001"]


class FakePrivateMessageEvent:
    raw_message = "hello"
    to_me = True

    def get_type(self) -> str:
        return "message"

    def get_user_id(self) -> str:
        return "42"


class FakeGroupMessageEvent(FakePrivateMessageEvent):
    group_id = 7
    raw_message = "/ping"
    to_me = False


class BotEventInterceptorTest(unittest.TestCase):
    def handle_same_event_on_both_bots(self, event_type, config):
        async def run_test():
            handled_by: list[str] = []
            sent_by: list[str] = []
            bots = {
                "1001": FakeBot("1001", handled_by, sent_by),
                "1002": FakeBot("1002", handled_by, sent_by),
            }

            with (
                patch.object(interceptor_module, "get_bots", return_value=bots),
                patch.object(interceptor_module, "_get_config", return_value=config),
                patch.object(
                    interceptor_module, "get_balancer", return_value=FakeBalancer()
                ),
            ):
                interceptor = interceptor_module.BotEventInterceptor()
                interceptor._event_pair_wait = 0
                interceptor.patch_handle_event()

                try:
                    await asyncio.gather(
                        bots["1001"].handle_event(event_type()),
                        bots["1002"].handle_event(event_type()),
                    )
                finally:
                    interceptor.unpatch_handle_event()

            return sorted(handled_by), sorted(sent_by)

        return asyncio.run(run_test())

    def test_private_messages_are_handled_by_each_receiving_bot(self):
        config = ScopedConfig(
            balance_mode="send",
            primary_bot_ids="1001",
            skip_balance_commands=[],
        )

        handled_by, sent_by = self.handle_same_event_on_both_bots(
            FakePrivateMessageEvent, config
        )

        self.assertEqual(handled_by, ["1001", "1002"])
        self.assertEqual(sent_by, ["1001", "1002"])

    def test_group_commands_are_still_distributed(self):
        config = ScopedConfig(balance_mode="send", skip_balance_commands=[])

        handled_by, sent_by = self.handle_same_event_on_both_bots(
            FakeGroupMessageEvent, config
        )

        self.assertEqual(handled_by, ["1001"])
        self.assertEqual(sent_by, [])
