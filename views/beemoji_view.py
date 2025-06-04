import discord
import traceback
import aiohttp
import io
import asyncio
from PIL import Image

from config import config
from utils.embed_utils import SafeEmbed
from utils.error_handler import send_error_embed
from utils.logger import discord_logger
from views.base_view import BaseImageView


class BeemojiView(BaseImageView):
    """View for beemoji command with add-to-server and edit functionality."""

    def __init__(
        self, emoji1_name: str, emoji2_name: str, generated_name: str = None
    ) -> None:
        self.emoji1_name = emoji1_name
        self.emoji2_name = emoji2_name
        self.generated_name = generated_name
        super().__init__(timeout=None)

    def setup_buttons(self) -> None:
        """Setup buttons specific to beemoji command."""
        # Add edit button
        self.add_item(
            discord.ui.Button(
                label="Edit",
                style=discord.ButtonStyle.secondary,
                custom_id="beemoji-edit-button",
                emoji=f"<:edit:{config.bot.emojis['edit_emoji_id']}>",
            )
        )

        # Add to server button
        self.add_item(
            discord.ui.Button(
                label="Add to Server",
                style=discord.ButtonStyle.primary,
                custom_id="beemoji-add-button",
                emoji="🔗",
            )
        )

    def _get_bookmark_type(self) -> str:
        return "🐝 Beemoji"  # Beemoji bookmark

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Handle button interactions."""
        custom_id = interaction.data["custom_id"]

        if custom_id == "beemoji-edit-button":
            await self.edit(interaction)
            return True
        elif custom_id == "beemoji-add-button":
            await self.add_to_server(interaction)
            return True

        return await super().interaction_check(interaction)

    async def reduce_image_size(
        self, image_data: bytes, width: int, height: int
    ) -> bytes:
        """Reduce the size of the image to the given width and height"""
        loop = asyncio.get_event_loop()
        image = await loop.run_in_executor(None, Image.open, io.BytesIO(image_data))
        image = await loop.run_in_executor(
            None, lambda: image.resize((width, height), Image.Resampling.LANCZOS)
        )
        buffer = io.BytesIO()
        await loop.run_in_executor(None, lambda: image.save(buffer, format="PNG"))
        return buffer.getvalue()

    async def edit(self, interaction: discord.Interaction) -> None:
        """Open edit modal for the beemoji."""
        from views.imagine_view import EditImageModal

        try:
            # Check if gptimage model is available
            if "gptimage" not in config.MODELS:
                await send_error_embed(
                    interaction,
                    "🎨 Model Unavailable",
                    "The gptimage model is currently not available for editing. Please try again later.",
                    delete_after_minutes=2,
                )
                return

            # Get the original image URL from the message embed (thumbnail for beemoji)
            if (
                not interaction.message.embeds
                or not interaction.message.embeds[0].thumbnail
            ):
                await send_error_embed(
                    interaction,
                    "🎨 No Image Found",
                    "Could not find the original emoji to edit.",
                    delete_after_minutes=1,
                )
                return

            original_image_url = interaction.message.embeds[0].thumbnail.url
            original_prompt = (
                f"A remixed version of {self.emoji1_name} and {self.emoji2_name} emojis"
            )

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
            await send_error_embed(
                interaction,
                "🎨 Error Opening Edit Dialog",
                f"```\n{str(e)}\n```",
                delete_after_minutes=2,
            )

    async def add_to_server(self, interaction: discord.Interaction) -> None:
        """Add the beemoji to the server as a custom emoji."""
        try:
            # Check if user has manage emojis permission
            if not interaction.user.guild_permissions.manage_emojis:
                await send_error_embed(
                    interaction,
                    "❌ Insufficient Permissions",
                    "You need the 'Manage Emojis and Stickers' permission to add emojis to this server.",
                    delete_after_minutes=1,
                )
                return

            # Get the image URL from the embed thumbnail
            if (
                not interaction.message.embeds
                or not interaction.message.embeds[0].thumbnail
            ):
                await send_error_embed(
                    interaction,
                    "❌ No Image Found",
                    "Could not find the emoji image to add to server.",
                    delete_after_minutes=1,
                )
                return

            image_url = interaction.message.embeds[0].thumbnail.url

            await interaction.response.defer(thinking=True, ephemeral=True)

            # Download the image
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status != 200:
                        raise Exception(
                            f"Failed to download image: HTTP {response.status}"
                        )

                    image_data = await response.read()
                    # reduce the size of the image to 80x80 pixels
                    image_data = await self.reduce_image_size(image_data, 80, 80)

            # Try to get emoji name from embed or use generated name
            emoji_name = self.generated_name
            try:
                # Try to extract from embed field
                for field in interaction.message.embeds[0].fields:
                    if field.name == "🏷️ Generated Name":
                        emoji_name = field.value.split("```")[1].strip()
                        break
            except (IndexError, AttributeError):
                pass

            if not emoji_name:
                emoji_name = f"beemoji_{self.emoji1_name}_{self.emoji2_name}"[:32]

            # Add emoji to server
            emoji = await interaction.guild.create_custom_emoji(
                name=emoji_name,
                image=image_data,
                reason=f"Beemoji created by {interaction.user}",
            )

            # Disable the add to server button
            for item in self.children:
                if (
                    isinstance(item, discord.ui.Button)
                    and item.custom_id == "beemoji-add-button"
                ):
                    item.disabled = True
                    break
            await interaction.message.edit(view=self)

            discord_logger.log_bot_event(
                action="beemoji_add_to_server",
                status="success",
                details={
                    "user_id": interaction.user.id,
                    "guild_id": interaction.guild_id,
                    "emoji_name": emoji_name,
                },
            )

            await interaction.followup.send(
                embed=SafeEmbed(
                    title="✅ Emoji Added Successfully!",
                    description=f"The beemoji has been added to the server as {emoji} `:{emoji_name}:`",
                    color=int(config.ui.colors.success, 16),
                ),
                ephemeral=True,
            )

        except discord.HTTPException as e:
            error_message = "Failed to add emoji to server."
            if e.code == 30008:
                error_message = "The server has reached the maximum number of emojis."
            elif e.code == 50035:
                error_message = "Invalid emoji name or the name is already taken."

            discord_logger.log_error(
                error_type="emoji_add_error",
                error_message=str(e),
                context={
                    "user_id": interaction.user.id,
                    "guild_id": interaction.guild_id,
                    "error_code": getattr(e, "code", None),
                },
            )

            await send_error_embed(
                interaction,
                "❌ Failed to Add Emoji",
                f"```\n{error_message}\n```",
                delete_after_minutes=2,
            )
        except Exception as e:
            discord_logger.log_error(
                error_type="add_emoji_error",
                error_message=str(e),
                traceback=traceback.format_exc(),
                context={
                    "user_id": interaction.user.id,
                    "guild_id": interaction.guild_id if interaction.guild else None,
                },
            )
            await send_error_embed(
                interaction,
                "❌ Error Adding Emoji",
                f"```\n{str(e)}\n```",
                delete_after_minutes=2,
            )
