"""
Bot Load Balancer Plugin Configuration

This module defines the configuration options for the bot load balancer plugin.
All configuration items use the 'bot_load_balancer__' prefix.
"""

from pydantic import BaseModel, Field


class Config(BaseModel):
    """Bot Load Balancer Configuration"""

    # Whether to enable bot load balancing
    enabled: bool = Field(
        default=True,
        validation_alias="bot_load_balancer__enabled",
        description="Enable or disable bot load balancing",
    )

    # Whether to enable sticky session (prefer last used bot)
    sticky_session: bool = Field(
        default=False,
        validation_alias="bot_load_balancer__sticky_session",
        description="Enable sticky session to prefer the last used bot in a session",
    )

    # Minimum interval between replies for the same bot (in seconds)
    min_reply_interval: float = Field(
        default=5.0,
        validation_alias="bot_load_balancer__min_reply_interval",
        description="Minimum interval between replies for the same bot in seconds",
    )

    # Commands to skip load balancing (for stateful plugins like games)
    skip_balance_commands: list[str] = Field(
        default_factory=lambda: [],
        validation_alias="bot_load_balancer__skip_balance_commands",
        description="Commands that should not be load balanced",
    )

    # Mode: 'event' or 'send'
    # - 'event': Balance at event receiving (current behavior)
    # - 'send': All bots receive events, balance only at sending
    balance_mode: str = Field(
        default="send",
        validation_alias="bot_load_balancer__balance_mode",
        description="Load balance mode: 'event' or 'send'",
    )

    # Primary bot for event handling (only used in 'send' mode)
    # If empty, uses the first connected bot
    primary_bot_id: str = Field(
        default="",
        validation_alias="bot_load_balancer__primary_bot_id",
        description="Primary bot ID for event handling in 'send' mode",
    )
