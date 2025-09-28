import discord
import traceback

from config import config
from utils.embed_utils import SafeEmbed
from utils.logger import discord_logger
from views.base_view import BaseImageView


class MultiPollinateView(BaseImageView):
    """View for multi-pollinate command with upscale functionality."""

    def __init__(self, image_count: int = 4) -> None:
        self.image_count = image_count
        super().__init__(timeout=None)

    def setup_buttons(self) -> None:
        """Setup buttons specific to multi-pollinate command."""
        # Add upscale buttons for each image
        for i in range(self.image_count):
            self.add_item(
                discord.ui.Button(
                    label=f"U{i + 1}",
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"U{i + 1}",
                )
            )

    def _get_bookmark_type(self) -> str:
        return "Multi-Pollinate"  # Multi-pollinate bookmark

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Handle button interactions."""
        custom_id = interaction.data["custom_id"]

        if custom_id.startswith("U"):
            index = int(custom_id[1]) - 1
            await self.upscale_image(interaction, index)
            await self.disable_button(interaction, custom_id)
            return True

        return await super().interaction_check(interaction)

    async def upscale_image(self, interaction: discord.Interaction, index: int) -> None:
        """Upscale and regenerate a specific image from the multi-pollinate grid."""
        await interaction.response.defer(ephemeral=True)

        try:
            # This would call the actual upscale/regeneration logic
            # For now, we'll show a placeholder message
            await interaction.followup.send(
                embed=SafeEmbed(
                    title=f"Upscaling Image {index + 1}",
                    description="This feature will be implemented with the actual upscale logic.",
                    color=int(config.ui.colors.info, 16),
                ),
                ephemeral=True,
            )

        except Exception as e:
            discord_logger.log_error(
                error_type="upscale_error",
                error_message=str(e),
                traceback=traceback.format_exc(),
                context={
                    "user_id": interaction.user.id,
                    "image_index": index,
                },
            )
            await interaction.followup.send(
                embed=SafeEmbed(
                    title="Error Upscaling Image",
                    description=f"```\n{str(e)}\n```",
                    color=int(config.ui.colors.error, 16),
                ),
                ephemeral=True,
            )

    async def disable_button(
        self, interaction: discord.Interaction, custom_id: str
    ) -> None:
        """Disable the button after it's been used."""
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.custom_id == custom_id:
                item.disabled = True
                break

        await interaction.message.edit(view=self)
