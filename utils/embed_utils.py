import discord
from typing import Any, Dict, Optional
import datetime
import random
from config import config

__all__: list[str] = ("generate_pollinate_embed", "generate_error_message", "SafeEmbed")


# Decorator to handle argument truncation in SafeEmbed methods
def _truncate_args(**limits):
    """
    Decorator that automatically truncates specified arguments to their Discord limits.
    
    Args:
        **limits: Mapping of argument names to their maximum character limits
        
    Example:
        @_truncate_args(name=256, value=1024)
        def add_field(self, *, name: str, value: str, inline: bool = True):
            ...
    """
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            for arg, max_len in limits.items():
                if arg in kwargs and kwargs[arg] is not None:
                    kwargs[arg] = self._truncate_text(kwargs[arg], max_len)
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


class SafeEmbed(discord.Embed):
    """
    A wrapper around discord.Embed that automatically handles Discord's character limits
    to prevent 400 Bad Request errors.

    Discord Limits:
    - Title: 256 characters
    - Description: 4096 characters
    - Field name: 256 characters
    - Field value: 1024 characters
    - Footer text: 2048 characters
    - Author name: 256 characters
    - Total embed: 6000 characters
    """

    def __init__(self, **kwargs):
        # Truncate title if needed
        if "title" in kwargs and kwargs["title"]:
            kwargs["title"] = self._truncate_text(kwargs["title"], 256)

        # Truncate description if needed
        if "description" in kwargs and kwargs["description"]:
            kwargs["description"] = self._truncate_text(kwargs["description"], 4096)

        super().__init__(**kwargs)

    @staticmethod
    def _truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
        """Truncate text to fit within Discord's character limits"""
        if not text:
            return text

        text = str(text)
        if len(text) <= max_length:
            return text

        # Check if text is wrapped in code blocks
        is_code_block = text.startswith("```") and text.endswith("```")

        if is_code_block:
            # For code blocks, we need to preserve the ``` at both ends
            # Remove the opening and closing ``` temporarily
            inner_text = text[3:-3]

            # Calculate available space for inner content
            # We need space for: opening ```, closing ```, and suffix
            available_space = (
                max_length - 6 - len(suffix)
            )  # 6 = 3 for opening + 3 for closing

            if available_space <= 0:
                # If we can't fit anything, just return truncated original
                truncate_length = max_length - len(suffix)
                return (
                    text[:truncate_length] + suffix
                    if truncate_length > 0
                    else suffix[:max_length]
                )

            if len(inner_text) <= available_space:
                return text  # No truncation needed

            # Truncate the inner content and rebuild
            truncated_inner = inner_text[:available_space] + suffix
            return f"```{truncated_inner}```"
        else:
            # Regular truncation for non-code-block text
            truncate_length = max_length - len(suffix)
            if truncate_length <= 0:
                return suffix[:max_length]

            return text[:truncate_length] + suffix

    @_truncate_args(name=256, value=1024)
    def add_field(self, *, name: str, value: str, inline: bool = True) -> "SafeEmbed":
        """Add a field with automatic truncation"""
        super().add_field(name=name, value=value, inline=inline)
        return self

    @_truncate_args(text=2048)
    def set_footer(
        self, *, text: Optional[str] = None, icon_url: Optional[str] = None
    ) -> "SafeEmbed":
        """Set footer with automatic text truncation"""
        super().set_footer(text=text, icon_url=icon_url)
        return self

    @_truncate_args(name=256)
    def set_author(
        self, *, name: str, url: Optional[str] = None, icon_url: Optional[str] = None
    ) -> "SafeEmbed":
        """Set author with automatic name truncation"""
        super().set_author(name=name, url=url, icon_url=icon_url)
        return self

    @_truncate_args(name=256, value=1024)
    def insert_field_at(
        self, index: int, *, name: str, value: str, inline: bool = True
    ) -> "SafeEmbed":
        """Insert field at index with automatic truncation"""
        super().insert_field_at(index, name=name, value=value, inline=inline)
        return self

    @_truncate_args(name=256, value=1024)
    def set_field_at(
        self, index: int, *, name: str, value: str, inline: bool = True
    ) -> "SafeEmbed":
        """Set field at index with automatic truncation"""
        super().set_field_at(index, name=name, value=value, inline=inline)
        return self

    @property
    def total_length(self) -> int:
        """Calculate total character count of the embed"""
        total = 0

        if self.title:
            total += len(self.title)
        if self.description:
            total += len(self.description)
        if self.footer and self.footer.text:
            total += len(self.footer.text)
        if self.author and self.author.name:
            total += len(self.author.name)

        for field in self.fields:
            total += len(field.name) + len(field.value)

        return total

    def is_within_limits(self) -> bool:
        """Check if embed is within Discord's 6000 character total limit"""
        return self.total_length <= 6000


async def generate_pollinate_embed(
    interaction: discord.Interaction,
    private: bool,
    dic: Dict[str, Any],
    time_taken: datetime.timedelta,
) -> SafeEmbed:
    embed = SafeEmbed(
        title="",
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        url=dic["url"],
    )

    embed.add_field(
        name="Prompt",
        value=f"```{dic['prompt']}```",
        inline=False,
    )

    if (
        len(dic["prompt"])
        < config.image_generation.validation.max_enhanced_prompt_length
        or dic["enhance"]
    ):
        if "enhanced_prompt" in dic and dic["enhanced_prompt"] is not None:
            embed.add_field(
                name="Enhanced Prompt",
                value=f"```{dic['enhanced_prompt']}```",
                inline=False,
            )

    embed.add_field(name="Seed", value=f"```{dic['seed']}```", inline=True)
    embed.add_field(
        name="Time Taken",
        value=f"```{round(time_taken.total_seconds(), 2)} s```",
        inline=True,
    )

    embed.add_field(name="", value="", inline=False)

    embed.add_field(name="Model", value=f"```{dic['model']}```", inline=True)
    embed.add_field(
        name="Dimensions", value=f"```{dic['width']}x{dic['height']}```", inline=True
    )

    if not private:
        embed.set_image(url="attachment://image.png")
    else:
        embed.set_image(url=dic["url"])

    embed.set_footer(text=f"Generated by {interaction.user}")

    return embed


async def generate_error_message(
    interaction: discord.Interaction,
    error,
    cooldown_configuration=None,
) -> SafeEmbed:
    if cooldown_configuration is None:
        cooldown_configuration: list[str] = [
            "- 1 time every 10 seconds",
        ]

    end_time = datetime.datetime.now() + datetime.timedelta(seconds=error.retry_after)
    end_time_ts = int(end_time.timestamp())

    embed = SafeEmbed(
        title="⏳ Cooldown",
        description=f"### You can use this command again <t:{end_time_ts}:R>",
        color=int(config.ui.colors.error, 16),
        timestamp=interaction.created_at,
    )
    embed.set_image(url=random.choice(config.resources.waiting_gifs))

    embed.add_field(
        name="How many times can I use this command?",
        value="\n".join(cooldown_configuration),
        inline=False,
    )

    try:
        embed.set_footer(
            text=f"{interaction.user} used /{interaction.command.name}",
            icon_url=interaction.user.avatar,
        )
    except Exception:
        embed.set_footer(
            text=f"{interaction.user} used /{interaction.command.name}",
            icon_url=interaction.user.default_avatar,
        )

    return embed


def ordinal(n) -> str:
    suffix: list[str] = ["th", "st", "nd", "rd"] + ["th"] * 6
    if 10 <= n % 100 <= 20:
        suffix_choice = "th"
    else:
        suffix_choice = suffix[n % 10]
    return f"{n}{suffix_choice}"
