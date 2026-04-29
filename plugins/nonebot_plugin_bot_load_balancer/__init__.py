"""
NoneBot Plugin: Bot Load Balancer

An independent, zero-intrusion bot load balancing plugin for NoneBot2.

Features:
- Reply-throttling based bot selection to prevent account bans
- Transparent event dispatch patch - works with ALL plugins (including third-party)
- Memory-based tracking with minimal overhead
- Configurable minimum reply intervals and sticky sessions

Configuration (in .env):
- bot_load_balancer__enabled: Enable/disable load balancing (default: True)
- bot_load_balancer__sticky_session: Enable sticky sessions (default: False)
- bot_load_balancer__min_reply_interval: Minimum seconds between replies (default: 5.0)
"""

from nonebot import get_driver, logger, get_plugin_config
from nonebot.adapters import Bot

from .config import Config

# Get driver and config
driver = get_driver()


@driver.on_startup
async def on_startup():
    """Initialize the load balancer on startup"""
    # Lazy import to avoid plugin detection issues
    from .balancer import init_balancer
    from .interceptor import init_interceptor

    # Initialize balancer and interceptor
    init_balancer()
    init_interceptor()

    from .interceptor import get_interceptor
    from .config import ScopedConfig

    plugin_config = get_plugin_config(Config).bot_load_balancer
    logger.info("[Bot Load Balancer] Starting up...")
    logger.info(
        "[Bot Load Balancer] Config: "
        f"sticky_session={plugin_config.sticky_session}, "
        f"min_reply_interval={plugin_config.min_reply_interval}s"
    )

    if plugin_config.enabled:
        try:
            interceptor = get_interceptor()
            interceptor.patch_handle_event()
            logger.success("[Bot Load Balancer] Successfully patched event dispatch")
        except Exception as e:
            logger.error(f"[Bot Load Balancer] Failed to patch event dispatch: {e}")

    if plugin_config.enabled:
        logger.success("[Bot Load Balancer] Plugin enabled")
    else:
        logger.info(
            "[Bot Load Balancer] Plugin disabled (set bot_load_balancer__enabled=true to enable)"
        )


@driver.on_bot_connect
async def on_bot_connect(bot: Bot):
    """Log newly connected bots and ensure dispatch patch is active."""
    logger.info(f"[Bot Load Balancer] Bot {bot.self_id} connected")

    from .config import Config
    if not get_plugin_config(Config).bot_load_balancer.enabled:
        return

    try:
        from .interceptor import get_interceptor

        interceptor = get_interceptor()
        interceptor.patch_handle_event()
    except Exception as e:
        logger.error(f"[Bot Load Balancer] Failed to patch event dispatch: {e}")


@driver.on_bot_disconnect
async def on_bot_disconnect(bot: Bot):
    """
    Clean up when a bot disconnects

    This hook is called when a bot disconnects from the NoneBot instance.
    We clean up any stored references to the disconnected bot.
    """
    logger.info(f"[Bot Load Balancer] Bot {bot.self_id} disconnected")

    from .config import Config
    if not get_plugin_config(Config).bot_load_balancer.enabled:
        return

    try:
        from .interceptor import get_interceptor

        interceptor = get_interceptor()
        interceptor.cleanup_disconnected_bot(bot.self_id)
        logger.debug(f"[Bot Load Balancer] Cleaned up bot {bot.self_id}")
    except Exception as e:
        logger.warning(f"[Bot Load Balancer] Failed to cleanup bot {bot.self_id}: {e}")


@driver.on_shutdown
async def on_shutdown():
    """Clean up on shutdown"""
    logger.info("[Bot Load Balancer] Shutting down...")

    from .config import Config
    if not get_plugin_config(Config).bot_load_balancer.enabled:
        return

    try:
        from .interceptor import get_interceptor

        interceptor = get_interceptor()
        interceptor.unpatch_handle_event()
        logger.success("[Bot Load Balancer] Successfully restored event dispatch")
    except Exception as e:
        logger.warning(
            f"[Bot Load Balancer] Failed to restore event dispatch during shutdown: {e}"
        )


# Export public API (lazy imports to avoid plugin detection issues)
__all__ = [
    "Config",
]
