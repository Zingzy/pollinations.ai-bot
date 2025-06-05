import datetime
import discord
import traceback

from config import config
from utils.embed_utils import SafeEmbed, generate_pollinate_embed
from utils.image_gen_utils import generate_image
from utils.pollinate_utils import parse_url
from utils.logger import discord_logger
from exceptions import APIError
from views.base_view import BaseImageView


class EditImageModal(discord.ui.Modal, title="Edit Image"):
    def __init__(self, original_image_url: str, original_prompt: str):
        super().__init__()
        self.original_image_url = original_image_url
        self.original_prompt = original_prompt

    edit_prompt = discord.ui.TextInput(
        label="Edit Prompt",
        placeholder="Describe how you want to modify the image...",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        from cogs.cross_pollinate_cog import (
            generate_cross_pollinate,
            generate_cross_pollinate_embed,
        )
        from views.cross_pollinate_view import CrossPollinateView

        try:
            await interaction.response.defer(thinking=True)

            start = datetime.datetime.now()

            # Use cross-pollinate functionality to edit the image
            dic, edited_image = await generate_cross_pollinate(
                prompt=self.edit_prompt.value,
                image_url=self.original_image_url,
                nologo=config.image_generation.defaults.nologo,
            )

            # Create the file attachment
            image_file = discord.File(edited_image, filename="edited_image.png")
            if dic.get("nsfw", False):
                image_file.filename = f"SPOILER_{image_file.filename}"

            time_taken_delta = datetime.datetime.now() - start
            embed = await generate_cross_pollinate_embed(
                interaction,
                False,
                dic,
                time_taken_delta,
                self.edit_prompt.value,
                self.original_image_url,
                image_file.filename,
            )

            # Send the edited image with cross-pollinate buttons
            view = CrossPollinateView()
            await interaction.followup.send(embed=embed, view=view, file=image_file)

        except Exception as e:
            discord_logger.log_error(
                error_type="edit_error",
                error_message=str(e),
                traceback=traceback.format_exc(),
                context={
                    "action": "edit_image",
                    "user_id": interaction.user.id,
                    "guild_id": interaction.guild_id if interaction.guild else None,
                },
            )
            await interaction.followup.send(
                embed=SafeEmbed(
                    title="🎨 Error Editing Image",
                    description=f"```\n{str(e)}\n```",
                    color=int(config.ui.colors.error, 16),
                ),
                ephemeral=True,
            )


class ImagineView(BaseImageView):
    """View for imagine/pollinate command with regenerate and edit functionality."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    def setup_buttons(self) -> None:
        """Setup buttons specific to imagine command."""
        # Add regenerate button
        self.add_item(
            discord.ui.Button(
                label="Regenerate",
                style=discord.ButtonStyle.secondary,
                custom_id="regenerate-button",
                emoji=f"<:redo:{config.bot.emojis['redo_emoji_id']}>",
            )
        )

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
        return ""  # Regular pollinate bookmark

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Handle button interactions."""
        custom_id = interaction.data["custom_id"]

        if custom_id == "regenerate-button":
            await self.regenerate(interaction)
            return True
        elif custom_id == "edit-button":
            await self.edit(interaction)
            return True

        return await super().interaction_check(interaction)

    async def regenerate(self, interaction: discord.Interaction) -> None:
        """Regenerate the image with the same parameters."""
        await interaction.response.send_message(
            embed=SafeEmbed(
                title="Regenerating Your Image",
                description="Please wait while we generate your image",
                color=int(config.ui.colors.success, 16),
            ),
            ephemeral=True,
        )

        start: datetime.datetime = datetime.datetime.now()
        data = await self.get_original_data(interaction)
        original_url = data["url"]
        prompt = data["prompt"]
        parsed_data: dict = parse_url(original_url)

        try:
            discord_logger.log_image_generation(
                action="regenerate_start",
                model=parsed_data.get("model", "unknown"),
                dimensions={
                    "width": parsed_data.get("width", 0),
                    "height": parsed_data.get("height", 0),
                },
                generation_time=0,
                status="started",
                cached=parsed_data.get("cached", False),
            )

            dic, image = await generate_image(prompt=prompt, **parsed_data)
            time_taken = (datetime.datetime.now() - start).total_seconds()

            discord_logger.log_image_generation(
                action="regenerate_complete",
                model=parsed_data.get("model", "unknown"),
                dimensions={
                    "width": parsed_data.get("width", 0),
                    "height": parsed_data.get("height", 0),
                },
                generation_time=time_taken,
                status="success",
                cached=parsed_data.get("cached", False),
            )

        except APIError as e:
            discord_logger.log_error(
                error_type="api_error",
                error_message=str(e),
                context={
                    "prompt": prompt,
                    "model": parsed_data.get("model", "unknown"),
                    "action": "regenerate",
                },
            )
            await interaction.followup.send(
                embed=SafeEmbed(
                    title="Couldn't Generate the Requested Image 😔",
                    description=f"```\n{e.message}\n```",
                    color=int(config.ui.colors.error, 16),
                ),
                ephemeral=True,
            )
            return
        except Exception as e:
            discord_logger.log_error(
                error_type="generation_error",
                error_message=str(e),
                traceback=traceback.format_exc(),
                context={
                    "prompt": prompt,
                    "model": parsed_data.get("model", "unknown"),
                    "action": "regenerate",
                },
            )
            await interaction.followup.send(
                embed=SafeEmbed(
                    title="Error",
                    description=f"Error generating image: {e}",
                    color=int(config.ui.colors.error, 16),
                ),
                ephemeral=True,
            )
            return

        image_file = discord.File(image, filename="image.png")
        if dic["nsfw"]:
            image_file.filename = f"SPOILER_{image_file.filename}"
        time_taken_delta: datetime.timedelta = datetime.datetime.now() - start

        embed: SafeEmbed = await generate_pollinate_embed(
            interaction, False, dic, time_taken_delta
        )

        await interaction.followup.send(
            embed=embed,
            file=image_file,
            view=ImagineView(),
        )

    async def edit(self, interaction: discord.Interaction) -> None:
        """Open edit modal for the image."""
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
