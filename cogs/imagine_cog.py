import datetime
import discord
from discord import app_commands
from discord.ext import commands

from constants import MODELS
from utils.image_gen_utils import generate_image, validate_dimensions, validate_prompt
from utils.embed_utils import generate_pollinate_embed, generate_error_message
from utils.pollinate_utils import parse_url
from utils.error_handler import send_error_embed
from exceptions import DimensionTooSmallError, PromptTooLongError, APIError
import traceback


class ImagineButtonView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Regenerate",
        style=discord.ButtonStyle.secondary,
        custom_id="regenerate-button",
        emoji="<:redo:1187101382101180456>",
    )
    async def regenerate(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Regenerating Your Image",
                description="Please wait while we generate your image",
                color=discord.Color.blurple(),
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
                    color=discord.Color.red(),
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
                    color=discord.Color.red(),
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
        emoji="<:delete:1187102382312652800>",
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
                        description="You can only delete the images prompted by you",
                        color=discord.Color.red(),
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
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

    @discord.ui.button(
        label="Bookmark",
        style=discord.ButtonStyle.secondary,
        custom_id="bookmark-button",
        emoji="<:save:1187101389822902344>",
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
                color=discord.Color.og_blurple(),
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
                    color=discord.Color.blurple(),
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
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return


class Imagine(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await self.bot.wait_until_ready()
        self.bot.add_view(ImagineButtonView())

    @app_commands.command(name="pollinate", description="Generate AI Images")
    @app_commands.choices(
        model=[app_commands.Choice(name=choice, value=choice) for choice in MODELS],
    )
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 10)
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
        width: int = 1000,
        height: int = 1000,
        model: app_commands.Choice[str] = MODELS[0],
        enhance: bool | None = None,
        safe: bool = False,
        cached: bool = False,
        nologo: bool = False,
        private: bool = False,
    ) -> None:
        validate_dimensions(width, height)
        validate_prompt(prompt)

        await interaction.response.defer(thinking=True, ephemeral=private)

        try:
            model = model.value
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
                cooldown_configuration=["- 1 time every 10 seconds"],
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
                interaction, "An unexprected error occurred", f"```\n{str(error)}\n```"
            )


async def setup(bot) -> None:
    await bot.add_cog(Imagine(bot))
    print("Imagine cog loaded")
