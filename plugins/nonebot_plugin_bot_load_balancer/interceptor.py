"""
Bot Load Balancer Interceptor

This module patches adapter bot event handlers so a balanced bot is selected
before the event reaches matchers.
"""

import functools
import asyncio
import time
from typing import Any

from nonebot import get_bots, logger
from nonebot.adapters import Bot, Event

from .balancer import get_balancer
from .config import Config


class BotEventInterceptor:
    """Event dispatch interceptor for session-level load balancing."""

    def __init__(self, config: Config):
        self.config = config
        self._original_handle_event_methods: dict[type[Bot], Any] = {}
        self._original_send_methods: dict[type[Bot], Any] = {}
        self._original_call_api_methods: dict[type[Bot], Any] = {}
        self._patched = False
        self._event_pair_lock = asyncio.Lock()
        self._pending_events: dict[str, dict[str, Any]] = {}
        self._resolved_events: dict[str, float] = {}
        self._event_pair_wait = 0.05
        self._resolved_event_ttl = 0.5
        self._current_event_context: dict[str, Event] = {}  # Track current event per bot

    def _should_balance(self, event: Event) -> bool:
        """Check if this event should use load balancing."""
        if self._is_bot_message(event):
            return False
        
        # Check if message starts with a skip command
        try:
            raw_message = getattr(event, "raw_message", None) or str(
                getattr(event, "message", "")
            )
            for skip_cmd in self.config.skip_balance_commands:
                if raw_message.strip().startswith(f"/{skip_cmd}") or raw_message.strip().startswith(skip_cmd):
                    logger.debug(
                        f"[Bot Load Balancer] Skipping load balance for command: {skip_cmd}"
                    )
                    return False
        except Exception:
            pass
        
        return hasattr(event, "group_id") or (
            hasattr(event, "scene") and hasattr(event.scene, "id")
        )

    def _is_bot_message(self, event: Event) -> bool:
        """Ignore messages sent by connected bots themselves."""
        try:
            return event.get_user_id() in get_bots()
        except Exception:
            return False

    def _get_session_id(self, event: Event) -> str | None:
        """Extract a stable session identifier from the event."""
        if hasattr(event, "group_id"):
            return str(event.group_id)
        if hasattr(event, "scene") and hasattr(event.scene, "id"):
            return str(event.scene.id)
        return None

    def _get_event_key(self, event: Event) -> str | None:
        """Build a stable key so the same incoming event is handled once."""
        session_id = self._get_session_id(event)
        if not session_id:
            return None

        user_id = None
        try:
            user_id = event.get_user_id()
        except Exception:
            pass

        raw_message = getattr(event, "raw_message", None) or str(
            getattr(event, "message", "")
        )
        return f"{event.get_type()}:{session_id}:{user_id}:{raw_message}"

    async def _resolve_paired_event(self, event_key: str):
        """Choose one arrived bot/event pair for this logical event."""
        await asyncio.sleep(self._event_pair_wait)

        async with self._event_pair_lock:
            pending = self._pending_events.pop(event_key, None)
            if pending is None:
                return

            self._resolved_events[event_key] = time.monotonic() + self._resolved_event_ttl

        session_id = pending["session_id"]
        arrivals: dict[str, tuple[Bot, Event, float]] = pending["arrivals"]
        waiters: dict[str, asyncio.Future[str | None]] = pending["waiters"]

        selected_bot_id: str | None = None
        if arrivals:
            arrival_times = {bot_id: arrived_at for bot_id, (_, _, arrived_at) in arrivals.items()}
            first_arrival_bot_id = min(arrival_times, key=arrival_times.get)
            first_arrival_at = arrival_times[first_arrival_bot_id]
            lag_ms = int((max(arrival_times.values()) - first_arrival_at) * 1000)

            if len(arrivals) == 1 or not session_id:
                selected_bot_id = next(iter(arrivals))
            else:
                try:
                    balancer = get_balancer()
                    selected_bot = await balancer.select_bot(
                        session_id,
                        candidate_bots={
                            bot_id: bot for bot_id, (bot, _, _) in arrivals.items()
                        },
                        sticky=self.config.sticky_session,
                    )
                    if selected_bot is not None:
                        selected_bot_id = selected_bot.self_id
                except Exception as e:
                    logger.warning(
                        f"[Bot Load Balancer] Failed to select paired bot, using first arrival: {e}"
                    )

            if selected_bot_id is None:
                selected_bot_id = next(iter(arrivals))

            logger.info(
                f"[Bot Load Balancer] Paired event key {event_key} with {len(arrivals)} "
                f"arrival(s), lag={lag_ms}ms, selected={selected_bot_id}"
            )

            if selected_bot_id != first_arrival_bot_id:
                logger.info(
                    f"[Bot Load Balancer] Switched bot: {first_arrival_bot_id} -> "
                    f"{selected_bot_id} for session {session_id}"
                )

        for bot_id, waiter in waiters.items():
            if waiter.done():
                continue
            waiter.set_result(bot_id if bot_id == selected_bot_id else None)

    async def _pair_event(self, bot: Bot, event: Event) -> str | None:
        """Wait briefly for duplicate deliveries, then pick one bot-owned event."""
        event_key = self._get_event_key(event)
        if not event_key:
            return bot.self_id

        async with self._event_pair_lock:
            now = time.monotonic()
            expired_keys = [
                key
                for key, expires_at in self._resolved_events.items()
                if expires_at <= now
            ]
            for key in expired_keys:
                self._resolved_events.pop(key, None)

            if event_key in self._resolved_events:
                return None

            pending = self._pending_events.get(event_key)
            if pending is None:
                pending = {
                    "session_id": self._get_session_id(event),
                    "arrivals": {},
                    "waiters": {},
                    "resolver": None,
                }
                self._pending_events[event_key] = pending

            loop = asyncio.get_running_loop()
            waiter: asyncio.Future[str | None] = loop.create_future()
            pending["arrivals"][bot.self_id] = (bot, event, time.monotonic())
            pending["waiters"][bot.self_id] = waiter

            resolver = pending["resolver"]
            if resolver is None or resolver.done():
                pending["resolver"] = asyncio.create_task(
                    self._resolve_paired_event(event_key)
                )

        return await waiter

    async def _record_assignment(self, bot_id: str, session_id: str) -> bool:
        """Record that a bot starts handling an event."""
        try:
            balancer = get_balancer()
            await balancer.record_assignment(bot_id, session_id)
            return True
        except Exception as e:
            logger.debug(f"[Bot Load Balancer] Failed to record assignment: {e}")
            return False

    async def _release_assignment(self, bot_id: str, session_id: str):
        """Release the active task slot after an event finishes."""
        try:
            balancer = get_balancer()
            await balancer.release_assignment(bot_id, session_id)
        except Exception as e:
            logger.debug(f"[Bot Load Balancer] Failed to release assignment: {e}")

    def patch_handle_event(self):
        """Patch connected bot classes' event entrypoints and send methods."""
        patched_classes = 0

        for bot in get_bots().values():
            bot_class = type(bot)
            
            # Patch handle_event
            if bot_class not in self._original_handle_event_methods:
                original_handle_event = bot_class.handle_event
                self._original_handle_event_methods[bot_class] = original_handle_event

                @functools.wraps(original_handle_event)
                async def intercepted_handle_event(
                    bot_self: Bot,
                    event: Event,
                    __original_handle_event=original_handle_event,
                ):
                    # In 'send' mode, only primary bot handles events
                    if self.config.balance_mode == "send":
                        primary_bot_id = self.config.primary_bot_id or min(get_bots().keys())
                        if bot_self.self_id != primary_bot_id:
                            # Not primary bot, skip this event
                            return None
                        
                        # Primary bot, store context and handle
                        self._current_event_context[bot_self.self_id] = event
                        try:
                            return await __original_handle_event(bot_self, event)
                        finally:
                            self._current_event_context.pop(bot_self.self_id, None)
                    
                    # Original 'event' mode logic
                    if not self._should_balance(event):
                        return await __original_handle_event(bot_self, event)

                    selected_bot_id = await self._pair_event(bot_self, event)
                    if selected_bot_id is None:
                        logger.info(
                            "[Bot Load Balancer] Skipped duplicate event delivery for "
                            f"session {self._get_session_id(event)} "
                            f"key {self._get_event_key(event)}"
                        )
                        return None

                    if selected_bot_id and selected_bot_id != bot_self.self_id:
                        return None

                    # Store current event context for this bot
                    self._current_event_context[bot_self.self_id] = event
                    
                    try:
                        return await __original_handle_event(bot_self, event)
                    finally:
                        # Clean up event context
                        self._current_event_context.pop(bot_self.self_id, None)

                bot_class.handle_event = intercepted_handle_event
                patched_classes += 1
                logger.info(
                    f"[Bot Load Balancer] Patched {bot_class.__module__}.{bot_class.__name__}.handle_event"
                )
            
            # Patch send method (only for logging, actual switching in call_api)
            if bot_class not in self._original_send_methods:
                original_send = bot_class.send
                self._original_send_methods[bot_class] = original_send
                interceptor_self = self  # Capture self reference
                
                @functools.wraps(original_send)
                async def intercepted_send(
                    bot_self: Bot,
                    event: Event,
                    message,
                    __original_send=original_send,
                    **kwargs
                ):
                    # In 'send' mode, don't do anything here - switching happens in call_api
                    # Just pass through to original send which will call call_api
                    return await __original_send(bot_self, event, message, **kwargs)
                
                bot_class.send = intercepted_send
                logger.info(
                    f"[Bot Load Balancer] Patched {bot_class.__module__}.{bot_class.__name__}.send"
                )
            
            # Patch call_api method to catch direct API calls
            if bot_class not in self._original_call_api_methods:
                original_call_api = bot_class.call_api
                self._original_call_api_methods[bot_class] = original_call_api
                interceptor_self = self  # Capture self reference
                
                @functools.wraps(original_call_api)
                async def intercepted_call_api(
                    bot_self: Bot,
                    api: str,
                    __original_call_api=original_call_api,
                    **data
                ):
                    # Check if this is a send message API
                    if api in ["send_msg", "send_group_msg", "send_private_msg"]:
                        # Try to get session from current event context or API data
                        session_id = None
                        if bot_self.self_id in interceptor_self._current_event_context:
                            event = interceptor_self._current_event_context[bot_self.self_id]
                            session_id = interceptor_self._get_session_id(event)
                        elif "group_id" in data:
                            session_id = str(data["group_id"])
                        elif "user_id" in data:
                            session_id = str(data["user_id"])
                        
                        # In 'send' mode, select a different bot to actually send
                        if interceptor_self.config.balance_mode == "send" and session_id:
                            try:
                                balancer = get_balancer()
                                selected_bot = await balancer.select_bot(
                                    session_id,
                                    candidate_bots=get_bots(),
                                    sticky=interceptor_self.config.sticky_session,
                                )
                                
                                logger.info(
                                    f"[Bot Load Balancer] API {api}: current={bot_self.self_id}, selected={selected_bot.self_id if selected_bot else None}"
                                )
                                
                                if selected_bot and selected_bot.self_id != bot_self.self_id:
                                    # Verify selected bot is still online
                                    online_bots = get_bots()
                                    if selected_bot.self_id not in online_bots:
                                        logger.warning(
                                            f"[Bot Load Balancer] Selected bot {selected_bot.self_id} is offline, using current bot {bot_self.self_id}"
                                        )
                                        # Record for current bot instead
                                        if session_id:
                                            await interceptor_self._record_assignment(bot_self.self_id, session_id)
                                    else:
                                        logger.info(
                                            f"[Bot Load Balancer] Switching {api}: {bot_self.self_id} → {selected_bot.self_id} for session {session_id}"
                                        )
                                        # Record assignment for the bot that actually sends
                                        await interceptor_self._record_assignment(selected_bot.self_id, session_id)
                                        # Get original call_api method for the selected bot
                                        selected_bot_class = type(selected_bot)
                                        original_call_api_method = interceptor_self._original_call_api_methods.get(selected_bot_class, selected_bot.call_api)
                                        # Use the selected bot's ORIGINAL call_api to avoid recursion
                                        return await original_call_api_method(selected_bot, api, **data)
                                
                            except Exception as e:
                                logger.warning(
                                    f"[Bot Load Balancer] Failed to switch bot for {api}: {e}, using original bot"
                                )
                        
                        if session_id:
                            logger.info(
                                f"[Bot Load Balancer] Bot {bot_self.self_id} calling {api} to session {session_id}"
                            )
                            await interceptor_self._record_assignment(bot_self.self_id, session_id)
                    
                    return await __original_call_api(bot_self, api, **data)
                
                bot_class.call_api = intercepted_call_api
                logger.info(
                    f"[Bot Load Balancer] Patched {bot_class.__module__}.{bot_class.__name__}.call_api"
                )

        self._patched = bool(self._original_handle_event_methods)
        if patched_classes:
            logger.info("[Bot Load Balancer] Patched bot event dispatch")
        elif not self._patched:
            logger.info("[Bot Load Balancer] No connected bots available to patch yet")
        else:
            logger.debug("[Bot Load Balancer] Bot event dispatch already patched")

    def unpatch_handle_event(self):
        """Restore original bot event entrypoints and send methods."""
        if not self._patched:
            return

        for bot_class, original_handle_event in self._original_handle_event_methods.items():
            bot_class.handle_event = original_handle_event
        
        for bot_class, original_send in self._original_send_methods.items():
            bot_class.send = original_send
        
        for bot_class, original_call_api in self._original_call_api_methods.items():
            bot_class.call_api = original_call_api

        self._original_handle_event_methods.clear()
        self._original_send_methods.clear()
        self._original_call_api_methods.clear()
        self._patched = False
        logger.info("[Bot Load Balancer] Restored bot event dispatch and send methods")

    def cleanup_disconnected_bot(self, bot_id: str):
        """Observe bot disconnects for logging/debugging."""
        logger.debug(f"[Bot Load Balancer] Observed disconnected bot {bot_id}")


_interceptor: BotEventInterceptor | None = None


def get_interceptor() -> BotEventInterceptor:
    """Get the global interceptor instance."""
    if _interceptor is None:
        raise RuntimeError(
            "BotEventInterceptor not initialized. Call init_interceptor() first."
        )
    return _interceptor


def init_interceptor(config: Config):
    """Initialize the global interceptor instance."""
    global _interceptor
    _interceptor = BotEventInterceptor(config)
    logger.success("[Bot Load Balancer] Interceptor initialized")
