import datetime
import discord
from discord import app_commands
from discord.ext import commands
import traceback

from config import config
from utils.image_gen_utils import generate_image, validate_dimensions, validate_prompt
from utils.embed_utils import generate_pollinate_embed, generate_error_message
from utils.pollinate_utils import parse_url
from utils.error_handler import send_error_embed
from exceptions import DimensionTooSmallError, PromptTooLongError, APIError


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
            embed=discord.Embed(
                title="Regenerating Your Image",
                description="Please wait while we generate your image",
                color=int(config.ui.colors.success, 16),
            ),
            ephemeral=True,
        )

        start: datetime.datetime = datetime.datetime.now()

        interaction_data: discord.Embed = interaction.message.embeds[0].to_dict()
        original_url: str | None = interaction.message.embeds[0].url

        prompt: str = interaction_data["fields"][0]["value"][3:-3]
        data: dict = parse_url(original_url)

        try:
            dic, image = await generate_image(prompt=prompt, **data)
        except APIError as e:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Couldn't Generate the Requested Image 😔",
                    description=f"```\n{e.message}\n```",
                    color=int(config.ui.colors.error, 16),
                ),
                ephemeral=True,
            )
            return
        except Exception as e:
            print(e, "\n", traceback.format_exc())
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error",
                    description=f"Error generating image : {e}",
                    color=int(config.ui.colors.error, 16),
                ),
                ephemeral=True,
            )
            return

        image_file = discord.File(image, filename="image.png")

        if dic["nsfw"]:
            image_file.filename = f"SPOILER_{image_file.filename}"

        time_taken: datetime.timedelta = datetime.datetime.now() - start

        embed: discord.Embed = await generate_pollinate_embed(
            interaction, False, dic, time_taken
        )

        await interaction.followup.send(
            embed=embed,
            file=image_file,
            view=ImagineButtonView(),
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
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="Error",
                        description=config.ui.error_messages["delete_unauthorized"],
                        color=int(config.ui.colors.error, 16),
                    ),
                    ephemeral=True,
                )
                return

            await interaction.message.delete()
            return
        except Exception as e:
            print(e, "\n", traceback.format_exc())
            await interaction.response.send_message(
                embed=discord.Embed(
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
            interaction_data: discord.Embed = interaction.message.embeds[0].to_dict()

            prompt: str = interaction_data["fields"][0]["value"][3:-3]
            url: str = interaction_data["url"]

            embed: discord.Embed = discord.Embed(
                description=f"**Prompt : {prompt}**",
                color=int(config.ui.colors.success, 16),
            )
            embed.add_field(
                name="",
                value=f"[Click here to view the image externally]({url})",
                inline=False,
            )
            embed.set_image(url=url)

            await interaction.user.send(embed=embed)

            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Image Bookmarked",
                    description="The image has been bookmarked and sent to your DMs",
                    color=int(config.ui.colors.success, 16),
                ),
                ephemeral=True,
            )
            return

        except Exception as e:
            print(e, "\n", traceback.format_exc())
            await interaction.response.send_message(
                embed=discord.Embed(
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
        prompt="Prompt of the Image you want want to generate",
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

        dic, image = await generate_image(
            prompt, width, height, model, safe, cached, nologo, enhance, private
        )

        image_file = discord.File(image, filename="image.png")
        if dic["nsfw"]:
            image_file.filename = f"SPOILER_{image_file.filename}"

        time_taken: datetime.timedelta = datetime.datetime.now() - start

        view: discord.ui.View = ImagineButtonView()
        embed: discord.Embed = await generate_pollinate_embed(
            interaction, private, dic, time_taken
        )

        if private:
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, view=view, file=image_file)
        return

    @imagine_command.error
    async def imagine_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CommandOnCooldown):
            embed: discord.Embed = await generate_error_message(
                interaction,
                error,
                cooldown_configuration=[
                    f"- {self.command_config.cooldown.rate} time every {self.command_config.cooldown.seconds} seconds",
                ],
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        elif isinstance(error, PromptTooLongError):
            await send_error_embed(
                interaction,
                "Prompt Too Long",
                f"```\n{str(error)}\n```",
            )

        elif isinstance(error, DimensionTooSmallError):
            await send_error_embed(
                interaction,
                "Dimensions Too Small",
                f"```\n{str(error)}\n```",
            )

        elif isinstance(error, APIError):
            await send_error_embed(
                interaction,
                "Couldn't Generate the Requested Image 😔",
                f"```\n{str(error)}\n```",
            )

        else:
            await send_error_embed(
                interaction,
                "An unexpected error occurred",
                f"```\n{str(error)}\n```",
            )


async def setup(bot) -> None:
    await bot.add_cog(Imagine(bot))
    print("Imagine cog loaded")
