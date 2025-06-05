import discord
import traceback
from abc import ABC, abstractmethod
from typing import Optional

from config import config
from utils.embed_utils import SafeEmbed
from utils.logger import discord_logger


class BaseImageView(discord.ui.View, ABC):
    """Base view class for image-related commands with common button functionality."""

    def __init__(self, timeout: Optional[float] = None) -> None:
        super().__init__(timeout=timeout)
        self.setup_buttons()

    @abstractmethod
    def setup_buttons(self) -> None:
        """Setup buttons specific to this view. Must be implemented by subclasses."""
        pass

    async def get_original_data(self, interaction: discord.Interaction) -> dict:
        """Extract original prompt and metadata from the embed."""
        interaction_data: dict = interaction.message.embeds[0].to_dict()

        # Find the prompt field (different commands use different field names)
        prompt = "Unknown prompt"
        for field in interaction_data.get("fields", []):
            if field["name"] in ["Prompt", "Cross-Pollinate Prompt 🐝"]:
                prompt = field["value"][3:-3]  # Remove ``` code block markers
                break

        original_url: Optional[str] = interaction.message.embeds[0].url

        return {
            "prompt": prompt,
            "url": original_url,
            "interaction_data": interaction_data,
        }

    @discord.ui.button(
        style=discord.ButtonStyle.red,
        custom_id="delete-button",
        emoji=f"<:delete:{config.bot.emojis['delete_emoji_id']}>",
    )
    async def delete(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Delete the message. Common functionality for all image commands."""
        try:
            author_id: int = interaction.message.interaction_metadata.user.id
            if (
                interaction.user.id != author_id
                and not interaction.user.guild_permissions.administrator
            ):
                discord_logger.log_error(
                    error_type="permission",
                    error_message="Unauthorized delete attempt",
                    context={
                        "user_id": interaction.user.id,
                        "author_id": author_id,
                        "guild_id": interaction.guild_id if interaction.guild else None,
                    },
                )
                await interaction.response.send_message(
                    embed=SafeEmbed(
                        title="Error",
                        description=config.ui.error_messages["delete_unauthorized"],
                        color=int(config.ui.colors.error, 16),
                    ),
                    ephemeral=True,
                )
                return

            await interaction.message.delete()
            discord_logger.log_bot_event(
                action="image_delete",
                status="success",
                details={
                    "user_id": interaction.user.id,
                    "guild_id": interaction.guild_id if interaction.guild else None,
                },
            )

        except Exception as e:
            discord_logger.log_error(
                error_type="delete_error",
                error_message=str(e),
                traceback=traceback.format_exc(),
                context={
                    "user_id": interaction.user.id,
                    "guild_id": interaction.guild_id if interaction.guild else None,
                },
            )
            await interaction.response.send_message(
                embed=SafeEmbed(
                    title="Error Deleting the Image",
                    description=f"{e}",
                    color=int(config.ui.colors.error, 16),
                ),
                ephemeral=True,
            )

    @discord.ui.button(
        label="Bookmark",
        style=discord.ButtonStyle.secondary,
        custom_id="bookmark-button",
        emoji=f"<:save:{config.bot.emojis['save_emoji_id']}>",
    )
    async def bookmark(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Bookmark the image. Common functionality for all image commands."""
        try:
            data = await self.get_original_data(interaction)
            prompt = data["prompt"]
            url = data["url"]

            # Determine the bookmark type based on the command
            bookmark_type = self._get_bookmark_type()

            embed: SafeEmbed = SafeEmbed(
                description=f"**{bookmark_type} Prompt: {prompt}**",
                color=int(config.ui.colors.success, 16),
            )
            embed.add_field(
                name="",
                value=f"[Click here to view the image externally]({url})",
                inline=False,
            )
            embed.set_image(url=url)
            await interaction.user.send(embed=embed)

            discord_logger.log_bot_event(
                action="image_bookmark",
                status="success",
                details={"user_id": interaction.user.id, "prompt": prompt, "url": url},
            )

            await interaction.response.send_message(
                embed=SafeEmbed(
                    title="Image Bookmarked",
                    description="The image has been bookmarked and sent to your DMs",
                    color=int(config.ui.colors.success, 16),
                ),
                ephemeral=True,
            )

        except Exception as e:
            discord_logger.log_error(
                error_type="bookmark_error",
                error_message=str(e),
                traceback=traceback.format_exc(),
                context={
                    "user_id": interaction.user.id,
                    "guild_id": interaction.guild_id if interaction.guild else None,
                },
            )
            await interaction.response.send_message(
                embed=SafeEmbed(
                    title="Error Bookmarking the Image",
                    description=f"{e}",
                    color=int(config.ui.colors.error, 16),
                ),
                ephemeral=True,
            )

    def _get_bookmark_type(self) -> str:
        """Get the bookmark type string. Override in subclasses for specific types."""
        return ""
