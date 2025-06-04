import discord
import traceback

from config import config
from utils.embed_utils import SafeEmbed
from utils.logger import discord_logger
from views.base_view import BaseImageView


class CrossPollinateView(BaseImageView):
    """View for cross-pollinate command with edit functionality."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    def setup_buttons(self) -> None:
        """Setup buttons specific to cross-pollinate command."""
        # Add edit button
        self.add_item(
            discord.ui.Button(
                label="Edit",
                style=discord.ButtonStyle.secondary,
                custom_id="edit-button",
                emoji=f"<:edit:{config.bot.emojis['edit_emoji_id']}>",
            )
        )

    def _get_bookmark_type(self) -> str:
        return "🐝 Cross-Pollinate"  # Cross-pollinate bookmark

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Handle button interactions."""
        custom_id = interaction.data["custom_id"]

        if custom_id == "edit-button":
            await self.edit(interaction)
            return True

        return await super().interaction_check(interaction)

    async def edit(self, interaction: discord.Interaction) -> None:
        """Open edit modal for the image."""
        from views.imagine_view import EditImageModal

        try:
            # Check if gptimage model is available
            if "gptimage" not in config.MODELS:
                await interaction.response.send_message(
                    embed=SafeEmbed(
                        title="🎨 Model Unavailable",
                        description="The gptimage model is currently not available for editing. Please try again later.",
                        color=int(config.ui.colors.warning, 16),
                    ),
                    ephemeral=True,
                )
                return

            # Get the original image URL from the message embed
            if (
                not interaction.message.embeds
                or not interaction.message.embeds[0].image
            ):
                await interaction.response.send_message(
                    embed=SafeEmbed(
                        title="🎨 No Image Found",
                        description="Could not find the original image to edit.",
                        color=int(config.ui.colors.error, 16),
                    ),
                    ephemeral=True,
                )
                return

            original_image_url = interaction.message.embeds[0].image.url
            data = await self.get_original_data(interaction)
            original_prompt = data["prompt"]

            # Show the edit modal
            modal = EditImageModal(original_image_url, original_prompt)
            await interaction.response.send_modal(modal)

        except Exception as e:
            discord_logger.log_error(
                error_type="edit_button_error",
                error_message=str(e),
                traceback=traceback.format_exc(),
                context={
                    "user_id": interaction.user.id,
                    "guild_id": interaction.guild_id if interaction.guild else None,
                },
            )
            await interaction.response.send_message(
                embed=SafeEmbed(
                    title="🎨 Error Opening Edit Dialog",
                    description=f"```\n{str(e)}\n```",
                    color=int(config.ui.colors.error, 16),
                ),
                ephemeral=True,
            )
