"""
Bot Load Balancer Core Logic

This module implements a reply-throttling based bot selection strategy.
"""

from datetime import datetime, timedelta
from typing import Optional

from nonebot import get_bots, logger
from nonebot.adapters import Bot

from .config import Config


class BotLoadBalancer:
    """Bot Load Balancer

    Implements bot selection based on:
    - Per-bot minimum reply interval to avoid fast repeated sends
    - Round-robin tie breaking within the same session
    """

    def __init__(self, config: Config):
        self.config = config
        self._last_bot_cache: dict[str, str] = {}
        self._global_last_reply_at: dict[str, datetime] = {}
        self._round_robin_index: dict[str, int] = {}

    async def select_bot(
        self,
        session_id: str,
        candidate_bots: Optional[dict[str, Bot]] = None,
        sticky: Optional[bool] = None,
    ) -> Optional[Bot]:
        """
        Select the best bot for the given session.

        Args:
            session_id: Group ID or user ID
            candidate_bots: Eligible bots for this event
            sticky: Whether to prefer the last used bot (None = use config default)

        Returns:
            Selected Bot instance, or None if no bots available
        """
        if not self.config.enabled:
            return None

        bots = candidate_bots if candidate_bots is not None else get_bots()
        if not bots:
            return None
        
        # Clean up tracking for offline bots
        online_bot_ids = set(bots.keys())
        offline_bot_ids = set(self._global_last_reply_at.keys()) - online_bot_ids
        for bot_id in offline_bot_ids:
            self._global_last_reply_at.pop(bot_id, None)
            logger.debug(f"[Bot Load Balancer] Cleaned up offline bot {bot_id}")

        if len(bots) == 1:
            # Only one bot, no need to balance
            return next(iter(bots.values()))

        # Check sticky session.
        use_sticky = sticky if sticky is not None else self.config.sticky_session
        if use_sticky and session_id in self._last_bot_cache:
            last_bot_id = self._last_bot_cache[session_id]
            if last_bot_id in bots:
                logger.debug(
                    f"[Bot Load Balancer] Using sticky session bot {last_bot_id} for {session_id}"
                )
                return bots[last_bot_id]

        current_time = datetime.now()
        min_reply_delta = timedelta(seconds=self.config.min_reply_interval)

        # Step 1: Filter out bots that replied too recently (within min_reply_interval)
        cooled_bots = {
            bot_id: bot
            for bot_id, bot in bots.items()
            if current_time - self._global_last_reply_at.get(bot_id, datetime.min)
            >= min_reply_delta
        }

        # Step 2: If all bots are cooled down, just round-robin among all
        if len(cooled_bots) == len(bots):
            bot_ids = sorted(bots)
            index = self._round_robin_index.get(session_id, 0) % len(bot_ids)
            selected_bot_id = bot_ids[index]
            self._round_robin_index[session_id] = index + 1
            self._last_bot_cache[session_id] = selected_bot_id
            logger.info(
                f"[Bot Load Balancer] Selected bot {selected_bot_id} for {session_id} "
                "(round-robin, all bots cooled)"
            )
            return bots[selected_bot_id]

        # Step 3: If only some bots are cooled, round-robin among cooled ones
        if len(cooled_bots) > 0:
            cooled_bot_ids = sorted(cooled_bots)
            index = self._round_robin_index.get(session_id, 0) % len(cooled_bot_ids)
            selected_bot_id = cooled_bot_ids[index]
            self._round_robin_index[session_id] = index + 1
            self._last_bot_cache[session_id] = selected_bot_id
            logger.info(
                f"[Bot Load Balancer] Selected bot {selected_bot_id} for {session_id} "
                f"(round-robin among {len(cooled_bots)} cooled bots)"
            )
            return cooled_bots[selected_bot_id]

        # Step 4: All bots are still in cooldown, pick the one that cooled longest ago
        bot_last_reply = {
            bot_id: self._global_last_reply_at.get(bot_id, datetime.min)
            for bot_id in bots
        }
        selected_bot_id = min(bot_last_reply, key=bot_last_reply.get)
        self._last_bot_cache[session_id] = selected_bot_id
        
        # Log cooldown status
        logger.info(
            f"[Bot Load Balancer] All bots in cooldown - "
            + ", ".join([
                f"{bot_id}: {(current_time - last_reply).total_seconds():.1f}s ago"
                for bot_id, last_reply in bot_last_reply.items()
                if last_reply != datetime.min
            ])
        )
        
        logger.info(
            f"[Bot Load Balancer] Selected bot {selected_bot_id} for {session_id} "
            "(all bots in cooldown, picked least recent)"
        )
        
        return bots[selected_bot_id]

    async def record_assignment(self, bot_id: str, session_id: str):
        """
        Record that a bot starts handling an event.

        Args:
            bot_id: Bot's self_id
            session_id: Group ID or user ID
        """
        current_time = datetime.now()
        self._global_last_reply_at[bot_id] = current_time

        logger.info(
            f"[Bot Load Balancer] Recorded reply from bot {bot_id} in {session_id} at {current_time.strftime('%H:%M:%S')}"
        )

    async def release_assignment(self, bot_id: str, session_id: str):
        """
        Release hook kept for interface compatibility.

        Args:
            bot_id: Bot's self_id
            session_id: Group ID or user ID
        """
        pass

    async def get_stats(self, session_id: str) -> dict[str, dict]:
        """
        Get current statistics for all bots in a session

        Args:
            session_id: Session ID to query

        Returns:
            Dictionary mapping bot_id to stats dict
        """
        return {
            bot_id: {
                "last_reply_at": last_reply_at.isoformat() if last_reply_at else None,
            }
            for bot_id, last_reply_at in self._global_last_reply_at.items()
        }


# Global instance
_balancer: Optional[BotLoadBalancer] = None


def get_balancer() -> BotLoadBalancer:
    """Get the global balancer instance"""
    if _balancer is None:
        raise RuntimeError(
            "BotLoadBalancer not initialized. Call init_balancer() first."
        )
    return _balancer


def init_balancer(config: Config):
    """Initialize the global balancer instance"""
    global _balancer
    _balancer = BotLoadBalancer(config)
    logger.success("[Bot Load Balancer] Balancer initialized")
