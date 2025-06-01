import datetime
import discord
from discord import app_commands
from discord.ext import commands
import traceback
import aiohttp
from urllib.parse import quote

from config import config
from utils.image_gen_utils import validate_prompt
from utils.embed_utils import (
    generate_error_message,
    SafeEmbed,
)
from utils.error_handler import send_error_embed
from utils.logger import discord_logger
from exceptions import PromptTooLongError, APIError


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
        try:
            # Validate the prompt
            validate_prompt(self.edit_prompt.value)

            await interaction.response.defer(thinking=True)

            start = datetime.datetime.now()
            discord_logger.log_image_generation(
                action="edit_start",
                model="gptimage",
                dimensions={"width": 0, "height": 0},
                generation_time=0,
                status="started",
                cached=False,
            )

            # Use cross-pollinate functionality to edit the image
            dic, edited_image = await generate_cross_pollinate(
                prompt=self.edit_prompt.value,
                image_url=self.original_image_url,
                nologo=config.image_generation.defaults.nologo,
            )

            time_taken = (datetime.datetime.now() - start).total_seconds()
            discord_logger.log_image_generation(
                action="edit_complete",
                model="gptimage",
                dimensions={"width": 0, "height": 0},
                generation_time=time_taken,
                status="success",
                cached=False,
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
            view = CrossPollinateButtonView()
            await interaction.followup.send(embed=embed, view=view, file=image_file)

        except PromptTooLongError as e:
            discord_logger.log_error(
                error_type="validation_error",
                error_message=str(e),
                context={"action": "edit_image", "error_type": "prompt_too_long"},
            )
            await interaction.followup.send(
                embed=SafeEmbed(
                    title="🎨 Prompt Too Long",
                    description=f"```\n{str(e)}\n```",
                    color=int(config.ui.colors.error, 16),
                ),
                ephemeral=True,
            )
        except APIError as e:
            discord_logger.log_error(
                error_type="api_error",
                error_message=str(e),
                context={"action": "edit_image"},
            )
            await interaction.followup.send(
                embed=SafeEmbed(
                    title="🎨 Couldn't Edit the Image 😔",
                    description=f"```\n{str(e)}\n```",
                    color=int(config.ui.colors.error, 16),
                ),
                ephemeral=True,
            )
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


class CrossPollinateButtonView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Edit",
        style=discord.ButtonStyle.secondary,
        custom_id="edit-button",
        emoji=f"<:edit:{config.bot.emojis['edit_emoji_id']}>",
    )
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
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

            # Get the original prompt based on the embed fields
            interaction_data: dict = interaction.message.embeds[0].to_dict()

            # Check if it's a cross-pollinate embed or regular pollinate embed
            prompt_field = None
            for field in interaction_data.get("fields", []):
                if field["name"] in ["Cross-Pollinate Prompt 🐝", "Prompt"]:
                    prompt_field = field
                    break

            original_prompt: str = (
                prompt_field["value"][3:-3] if prompt_field else "Unknown prompt"
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
            await interaction.response.send_message(
                embed=SafeEmbed(
                    title="🎨 Error Opening Edit Dialog",
                    description=f"```\n{str(e)}\n```",
                    color=int(config.ui.colors.error, 16),
                ),
                ephemeral=True,
            )

    @discord.ui.button(
        style=discord.ButtonStyle.red,
        custom_id="delete-button",
        emoji=f"<:delete:{config.bot.emojis['delete_emoji_id']}>",
    )
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
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
                action="cross_pollinate_delete",
                status="success",
                details={
                    "user_id": interaction.user.id,
                    "guild_id": interaction.guild_id if interaction.guild else None,
                },
            )
            return
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
            return

    @discord.ui.button(
        label="Bookmark",
        style=discord.ButtonStyle.secondary,
        custom_id="bookmark-button",
        emoji=f"<:save:{config.bot.emojis['save_emoji_id']}>",
    )
    async def bookmark(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        try:
            interaction_data: dict = interaction.message.embeds[0].to_dict()
            prompt_field = next(
                (
                    field
                    for field in interaction_data["fields"]
                    if field["name"] == "Cross-Pollinate Prompt 🐝"
                ),
                None,
            )
            prompt: str = (
                prompt_field["value"][3:-3] if prompt_field else "Unknown prompt"
            )
            url: str = interaction_data["url"]

            embed: SafeEmbed = SafeEmbed(
                description=f"**🐝 Cross-Pollinate Prompt: {prompt}**",
                color=int(config.ui.colors.success, 16),
            )
            embed.add_field(
                name="",
                value=f"[Click here to view the cross-pollinated image externally]({url})",
                inline=False,
            )
            embed.set_image(url=url)
            await interaction.user.send(embed=embed)

            discord_logger.log_bot_event(
                action="cross_pollinate_bookmark",
                status="success",
                details={"user_id": interaction.user.id, "prompt": prompt, "url": url},
            )
            await interaction.response.send_message(
                embed=SafeEmbed(
                    title="🐝 Image Bookmarked",
                    description="The cross-pollinated image has been bookmarked and sent to your DMs",
                    color=int(config.ui.colors.success, 16),
                ),
                ephemeral=True,
            )
            return
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
            return


async def generate_cross_pollinate(prompt: str, image_url: str, nologo: bool):
    """Generate an edited image using the gptimage model"""

    # Encode the image URL for the API
    encoded_image = quote(image_url, safe="")

    # Build the API URL with image parameter
    url: str = f"{config.api.image_gen_endpoint}/{prompt}"
    url += f"?image={encoded_image}"
    url += "&model=gptimage"
    url += f"&nologo={nologo}" if nologo else ""
    url += f"&referer={config.image_generation.referer}"

    dic = {
        "prompt": prompt,
        "image_url": image_url,
        "model": "gptimage",
        "nologo": nologo,
        "url": quote(url, safe=":/&=?"),
    }

    headers = {
        "Authorization": f"Bearer {config.api.api_key}",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, allow_redirects=True, headers=headers
            ) as response:
                if response.status >= 500:
                    raise APIError(
                        f"Server error occurred while editing image with status code: {response.status}\nPlease try again later"
                    )
                elif response.status == 429:
                    raise APIError(config.ui.error_messages["rate_limit"])
                elif response.status == 404:
                    raise APIError(config.ui.error_messages["resource_not_found"])
                elif response.status != 200:
                    raise APIError(
                        f"API request failed with status code: {response.status}",
                    )

                image_data = await response.read()

                if not image_data:
                    raise APIError("Received empty response from server")

                import io

                image_file = io.BytesIO(image_data)
                image_file.seek(0)

                # Set basic metadata
                dic["nsfw"] = False  # Default for image editing

        return (dic, image_file)
    except aiohttp.ClientError as e:
        raise APIError(f"Network error occurred: {str(e)}")


async def generate_cross_pollinate_embed(
    interaction: discord.Interaction,
    private: bool,
    dic: dict,
    time_taken: datetime.timedelta,
    prompt: str,
    original_image_url: str,
    file_name: str,
) -> SafeEmbed:
    """Generate embed for cross-pollinate results"""

    embed = SafeEmbed(
        title="",
        url=dic["url"],
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )

    embed.add_field(
        name="Cross-Pollinate Prompt 🐝",
        value=f"```{prompt}```",
        inline=False,
    )

    embed.add_field(
        name="Model Used",
        value="```gptimage```",
        inline=True,
    )

    embed.add_field(
        name="Processing Time",
        value=f"```{time_taken.total_seconds():.2f}s```",
        inline=True,
    )

    embed.add_field(
        name="Original Image",
        value=f"[Original Image]({original_image_url})",
        inline=False,
    )

    # Always use attachment reference since we send file attachments for both private and public
    embed.set_image(url=f"attachment://{file_name}")

    if not private:
        embed.set_user_footer(interaction, "🐝 Cross-pollinated by")

    return embed


class CrossPollinate(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.command_config = config.commands["cross-pollinate"]

    async def cog_load(self) -> None:
        await self.bot.wait_until_ready()
        self.bot.add_view(CrossPollinateButtonView())
        discord_logger.log_bot_event(
            action="cog_load", status="success", details={"cog": "CrossPollinate"}
        )

    @app_commands.command(
        name="cross-pollinate",
        description="🐝 Cross-pollinate images with AI using our worker bees",
    )
    @app_commands.guild_only()
    @app_commands.checks.cooldown(
        config.commands["cross-pollinate"].cooldown.rate,
        config.commands["cross-pollinate"].cooldown.seconds,
    )
    @app_commands.describe(
        image="The image you want to cross-pollinate (upload an image file)",
        prompt="Describe how you want to modify the image",
        nologo="Remove the Logo",
        private="Only you can see the cross-pollinated image if set to True",
    )
    async def cross_pollinate_command(
        self,
        interaction: discord.Interaction,
        image: discord.Attachment,
        prompt: str,
        nologo: bool = config.image_generation.defaults.nologo,
        private: bool = config.image_generation.defaults.private,
    ) -> None:
        # Validate the prompt
        validate_prompt(prompt)

        # Validate the attachment is an image
        if not image.content_type or not image.content_type.startswith("image/"):
            await interaction.response.send_message(
                embed=SafeEmbed(
                    title="🐝 Invalid File Type",
                    description="Please upload a valid image file (PNG, JPG, JPEG, GIF, WEBP)",
                    color=int(config.ui.colors.error, 16),
                ),
                ephemeral=True,
            )
            return

        # Check if gptimage model is available
        if "gptimage" not in config.MODELS:
            await interaction.response.send_message(
                embed=SafeEmbed(
                    title="🐝 Model Unavailable",
                    description="The gptimage model is currently not available. Please try again later when our worker bees have access to the cross-pollination tools.",
                    color=int(config.ui.colors.warning, 16),
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True, ephemeral=private)

        start: datetime.datetime = datetime.datetime.now()
        discord_logger.log_image_generation(
            action="cross_pollinate_start",
            model="gptimage",
            dimensions={"width": 0, "height": 0},  # Not applicable for editing
            generation_time=0,
            status="started",
            cached=False,
        )

        try:
            # Use the Discord CDN URL directly
            image_url = image.url

            dic, edited_image = await generate_cross_pollinate(
                prompt=prompt, image_url=image_url, nologo=nologo
            )
            time_taken = (datetime.datetime.now() - start).total_seconds()

            discord_logger.log_image_generation(
                action="cross_pollinate_complete",
                model="gptimage",
                dimensions={"width": 0, "height": 0},
                generation_time=time_taken,
                status="success",
                cached=False,
            )

            # Create the file attachment
            image_file = discord.File(
                edited_image, filename="cross_pollinated_image.png"
            )
            if dic.get("nsfw", False):
                image_file.filename = f"SPOILER_{image_file.filename}"

            time_taken_delta: datetime.timedelta = datetime.datetime.now() - start
            embed: SafeEmbed = await generate_cross_pollinate_embed(
                interaction,
                private,
                dic,
                time_taken_delta,
                prompt,
                image_url,
                image_file.filename,
            )

            if private:
                # For private responses, send embed with file attachment but no view
                await interaction.followup.send(
                    embed=embed, file=image_file, ephemeral=True
                )
            else:
                # For public responses, send embed with view and file attachment
                view: discord.ui.View = CrossPollinateButtonView()
                await interaction.followup.send(embed=embed, view=view, file=image_file)

        except Exception as e:
            discord_logger.log_error(
                error_type="generation_error",
                error_message=str(e),
                traceback=traceback.format_exc(),
                context={
                    "prompt": prompt,
                    "model": "gptimage",
                    "user_id": interaction.user.id,
                    "guild_id": interaction.guild_id if interaction.guild else None,
                },
            )
            raise
        return

    @cross_pollinate_command.error
    async def cross_pollinate_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CommandOnCooldown):
            discord_logger.log_error(
                error_type="cooldown",
                error_message=str(error),
                context={
                    "command": "cross-pollinate",
                    "user_id": interaction.user.id,
                    "retry_after": error.retry_after,
                },
            )
            embed: SafeEmbed = await generate_error_message(
                interaction,
                error,
                cooldown_configuration=[
                    f"- {self.command_config.cooldown.rate} time every {self.command_config.cooldown.seconds} seconds",
                ],
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        elif isinstance(error, PromptTooLongError):
            discord_logger.log_error(
                error_type="validation_error",
                error_message=str(error),
                context={"command": "cross-pollinate", "error_type": "prompt_too_long"},
            )
            await send_error_embed(
                interaction,
                "🐝 Prompt Too Long",
                f"```\n{str(error)}\n```",
            )
        elif isinstance(error, APIError):
            discord_logger.log_error(
                error_type="api_error",
                error_message=str(error),
                context={"command": "cross-pollinate"},
            )
            await send_error_embed(
                interaction,
                "🐝 Couldn't Cross-Pollinate the Image 😔",
                f"```\n{str(error)}\n```",
            )
        else:
            discord_logger.log_error(
                error_type="unexpected_error",
                error_message=str(error),
                traceback=traceback.format_exception_only(type(error), error),
                context={"command": "cross-pollinate", "user_id": interaction.user.id},
            )
            await send_error_embed(
                interaction,
                "🐝 An unexpected error occurred",
                f"```\n{str(error)}\n```",
            )


async def setup(bot) -> None:
    await bot.add_cog(CrossPollinate(bot))
    discord_logger.log_bot_event(
        action="cog_setup", status="success", details={"cog": "CrossPollinate"}
    )
