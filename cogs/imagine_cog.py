import datetime
import discord
from discord import app_commands
from discord.ext import commands
import traceback

from config import config
from utils.image_gen_utils import generate_image, validate_dimensions, validate_prompt
from utils.embed_utils import (
    generate_pollinate_embed,
    generate_error_message,
    SafeEmbed,
)
from utils.pollinate_utils import parse_url
from utils.error_handler import send_error_embed
from utils.logger import discord_logger
from exceptions import DimensionTooSmallError, PromptTooLongError, APIError

# Import cross-pollinate functionality for edit button
from cogs.cross_pollinate_cog import EditImageModal


class ImagineButtonView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Regenerate",
        style=discord.ButtonStyle.secondary,
        custom_id="regenerate-button",
        emoji=f"<:redo:{config.bot.emojis['redo_emoji_id']}>",
    )
    async def regenerate(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_message(
            embed=SafeEmbed(
                title="Regenerating Your Image",
                description="Please wait while we generate your image",
                color=int(config.ui.colors.success, 16),
            ),
            ephemeral=True,
        )

        start: datetime.datetime = datetime.datetime.now()
        interaction_data: dict = interaction.message.embeds[0].to_dict()
        original_url: str | None = interaction.message.embeds[0].url
        prompt: str = interaction_data["fields"][0]["value"][3:-3]
        data: dict = parse_url(original_url)

        try:
            discord_logger.log_image_generation(
                action="regenerate_start",
                model=data.get("model", "unknown"),
                dimensions={
                    "width": data.get("width", 0),
                    "height": data.get("height", 0),
                },
                generation_time=0,
                status="started",
                cached=data.get("cached", False),
            )

            dic, image = await generate_image(prompt=prompt, **data)
            time_taken = (datetime.datetime.now() - start).total_seconds()
            discord_logger.log_image_generation(
                action="regenerate_complete",
                model=data.get("model", "unknown"),
                dimensions={
                    "width": data.get("width", 0),
                    "height": data.get("height", 0),
                },
                generation_time=time_taken,
                status="success",
                cached=data.get("cached", False),
            )
        except APIError as e:
            discord_logger.log_error(
                error_type="api_error",
                error_message=str(e),
                context={
                    "prompt": prompt,
                    "model": data.get("model", "unknown"),
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
                    "model": data.get("model", "unknown"),
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
            view=ImagineButtonView(),
        )

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
            if not interaction.message.embeds or not interaction.message.embeds[0].image:
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
            
            # Get the original prompt
            interaction_data: dict = interaction.message.embeds[0].to_dict()
            original_prompt: str = interaction_data["fields"][0]["value"][3:-3]
            
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
                action="image_delete",
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
            prompt: str = interaction_data["fields"][0]["value"][3:-3]
            url: str = interaction_data["url"]
            embed: SafeEmbed = SafeEmbed(
                description=f"**Prompt: {prompt}**",
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


class Imagine(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.command_config = config.commands["pollinate"]

    async def cog_load(self) -> None:
        await self.bot.wait_until_ready()
        self.bot.add_view(ImagineButtonView())
        discord_logger.log_bot_event(
            action="cog_load", status="success", details={"cog": "Imagine"}
        )

    @app_commands.command(name="pollinate", description="Generate AI Images")
    @app_commands.choices(
        model=[
            app_commands.Choice(name=choice, value=choice) for choice in config.MODELS
        ],
    )
    @app_commands.guild_only()
    @app_commands.checks.cooldown(
        config.commands["pollinate"].cooldown.rate,
        config.commands["pollinate"].cooldown.seconds,
    )
    @app_commands.describe(
        prompt="Prompt of the Image you want to generate",
        height="Height of the Image",
        width="Width of the Image",
        model="Model to use for generating the Image",
        enhance="Enables AI Prompt Enhancement",
        safe="Whether the Image should be Safe for Work or not",
        cached="Uses the Default seed",
        nologo="Remove the Logo",
        private="Only you can see the generated Image if set to True",
    )
    async def imagine_command(
        self,
        interaction: discord.Interaction,
        prompt: str,
        width: int = config.commands["pollinate"].default_width,
        height: int = config.commands["pollinate"].default_height,
        model: app_commands.Choice[str] = config.MODELS[0],
        enhance: bool | None = config.image_generation.defaults.enhance,
        safe: bool = config.image_generation.defaults.safe,
        cached: bool = config.image_generation.defaults.cached,
        nologo: bool = config.image_generation.defaults.nologo,
        private: bool = config.image_generation.defaults.private,
    ) -> None:
        validate_dimensions(width, height)
        validate_prompt(prompt)
        await interaction.response.defer(thinking=True, ephemeral=private)
        try:
            model = model.value if model else None
        except Exception:
            pass

        start: datetime.datetime = datetime.datetime.now()
        discord_logger.log_image_generation(
            action="generate_start",
            model=model or "default",
            dimensions={"width": width, "height": height},
            generation_time=0,
            status="started",
            cached=cached,
        )
        try:
            dic, image = await generate_image(
                prompt, width, height, model, safe, cached, nologo, enhance, private
            )
            time_taken = (datetime.datetime.now() - start).total_seconds()
            discord_logger.log_image_generation(
                action="generate_complete",
                model=model or "default",
                dimensions={"width": width, "height": height},
                generation_time=time_taken,
                status="success",
                cached=cached,
            )
            image_file = discord.File(image, filename="image.png")
            if dic["nsfw"]:
                image_file.filename = f"SPOILER_{image_file.filename}"
            time_taken_delta: datetime.timedelta = datetime.datetime.now() - start
            embed: SafeEmbed = await generate_pollinate_embed(
                interaction, private, dic, time_taken_delta
            )
            if private:
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                # Use ImagineButtonView for public images to get edit functionality
                view: discord.ui.View = ImagineButtonView()
                await interaction.followup.send(embed=embed, view=view, file=image_file)
        except Exception as e:
            discord_logger.log_error(
                error_type="generation_error",
                error_message=str(e),
                traceback=traceback.format_exc(),
                context={
                    "prompt": prompt,
                    "model": model,
                    "width": width,
                    "height": height,
                    "user_id": interaction.user.id,
                    "guild_id": interaction.guild_id if interaction.guild else None,
                },
            )
            raise
        return

    @imagine_command.error
    async def imagine_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CommandOnCooldown):
            discord_logger.log_error(
                error_type="cooldown",
                error_message=str(error),
                context={
                    "command": "pollinate",
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
                context={"command": "pollinate", "error_type": "prompt_too_long"},
            )
            await send_error_embed(
                interaction,
                "Prompt Too Long",
                f"```\n{str(error)}\n```",
            )
        elif isinstance(error, DimensionTooSmallError):
            discord_logger.log_error(
                error_type="validation_error",
                error_message=str(error),
                context={"command": "pollinate", "error_type": "dimension_too_small"},
            )
            await send_error_embed(
                interaction,
                "Dimensions Too Small",
                f"```\n{str(error)}\n```",
            )
        elif isinstance(error, APIError):
            discord_logger.log_error(
                error_type="api_error",
                error_message=str(error),
                context={"command": "pollinate"},
            )
            await send_error_embed(
                interaction,
                "Couldn't Generate the Requested Image 😔",
                f"```\n{str(error)}\n```",
            )
        else:
            discord_logger.log_error(
                error_type="unexpected_error",
                error_message=str(error),
                traceback=traceback.format_exception_only(type(error), error),
                context={"command": "pollinate", "user_id": interaction.user.id},
            )
            await send_error_embed(
                interaction,
                "An unexpected error occurred",
                f"```\n{str(error)}\n```",
            )


async def setup(bot) -> None:
    await bot.add_cog(Imagine(bot))
    discord_logger.log_bot_event(
        action="cog_setup", status="success", details={"cog": "Imagine"}
    )
