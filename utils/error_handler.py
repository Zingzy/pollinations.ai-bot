from discord import Interaction
import discord
import datetime
import asyncio
from config import config
from typing import Optional
from utils.embed_utils import SafeEmbed


async def send_error_embed(
    interaction: Interaction,
    title: str,
    description: str = None,
    delete_after_minutes: Optional[int] = None,
) -> None:
    """
    Send a non-ephemeral error message that auto-deletes after the specified time.
    Includes a timer display showing when the message will be deleted.

    Args:
        interaction: Discord interaction object
        title: Error title
        description: Error description (optional)
        delete_after_minutes: Minutes until auto-deletion (default: None)
    """
    if not description:
        description = config.ui.error_messages["unknown"]

    # Calculate deletion time
    if delete_after_minutes:
        delete_time = datetime.datetime.now() + datetime.timedelta(
            minutes=delete_after_minutes
        )
        delete_time_ts = int(delete_time.timestamp())
    else:
        delete_time = None
        delete_time_ts = None

    # Create error embed with timer
    embed = SafeEmbed(
        title=f"❌ {title}",
        description=f"{description}",
        color=int(config.ui.colors.error, 16),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )

    if delete_time:
        embed.add_field(
            name="",
            value=f"-# This error message will be removed <t:{delete_time_ts}:R> to keep the chat clean.",
            inline=False,
        )

    # Set footer with user info
    if hasattr(interaction, "user"):
        embed.set_user_footer_with_text(
            interaction,
            f"Error occurred for {interaction.user.display_name} • \{interaction.command.name}",
        )

    # Send the message
    if not interaction.response.is_done():
        message = await interaction.response.send_message(embed=embed, ephemeral=True)
        # Get the message object for deletion
        message = await interaction.original_response()
    else:
        try:
            await interaction.followup.delete_previous_message()
        except Exception:
            pass
        message = await interaction.followup.send(embed=embed, ephemeral=True)

    # Schedule auto-deletion
    if delete_time:
        asyncio.create_task(_auto_delete_message(message, delete_after_minutes * 60))


async def _auto_delete_message(message: discord.Message, delay_seconds: int) -> None:
    """
    Helper function to auto-delete a message after the specified delay.

    Args:
        message: Discord message to delete
        delay_seconds: Delay in seconds before deletion
    """
    try:
        await asyncio.sleep(delay_seconds)
        await message.delete()
    except discord.NotFound:
        # Message was already deleted
        pass
    except discord.Forbidden:
        # Bot doesn't have permission to delete the message
        pass
    except Exception:
        # Any other error, fail silently
        pass
