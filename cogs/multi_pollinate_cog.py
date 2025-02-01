import datetime
import discord
from discord import app_commands
from discord.ext import commands
import traceback
import asyncio

from utils.embed_utils import generate_error_message
from utils.image_gen_utils import generate_image, validate_dimensions, validate_prompt
from utils.error_handler import send_error_embed
from exceptions import (
    NoImagesGeneratedError,
    ImageGenerationError,
    PromptTooLongError,
    DimensionTooSmallError,
    APIError,
)
from constants import MODELS


class multiImagineButtonView(discord.ui.View):
    def __init__(self, image_count=4) -> None:
        super().__init__(timeout=None)

        self.image_count: int = image_count
        self.create_buttons()

    def create_buttons(self) -> None:
        for i in range(self.image_count):
            self.add_item(
                discord.ui.Button(
                    label=f"U{i + 1}",
                    style=discord.ButtonStyle.secondary,
                    custom_id=f"U{i + 1}",
                )
            )
        self.add_item(
            discord.ui.Button(
                label="",
                style=discord.ButtonStyle.danger,
                custom_id="multiimagine_delete",
                emoji="<:delete:1187102382312652800>",
            )
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        custom_id = interaction.data["custom_id"]
        if custom_id.startswith("U"):
            index = int(custom_id[1]) - 1
            await self.regenerate_image(interaction, index)
            await self.disable_button(interaction, custom_id)
            return True
        elif custom_id == "multiimagine_delete":
            await self.delete_image(interaction)
            return True
        return False

    async def regenerate_image(self, interaction: discord.Interaction, index: int):
        await interaction.response.defer(ephemeral=True)
        embed, image = await Multi_pollinate.get_info(interaction, index)
        await interaction.followup.send(embed=embed, file=image)

    async def disable_button(self, interaction: discord.Interaction, custom_id: str):
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.custom_id == custom_id:
                item.disabled = True
                break

        await interaction.message.edit(view=self)

    async def delete_image(self, interaction: discord.Interaction):
        try:
            author_id: int = interaction.message.interaction_metadata.user.id

            if interaction.user.id != author_id:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="Error",
                        description="You can only delete your own images",
                        color=discord.Color.red(),
                    ),
                    ephemeral=True,
                )
                return

            return await interaction.message.delete()

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


class Multi_pollinate(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await self.bot.wait_until_ready()
        self.bot.add_view(multiImagineButtonView())

    async def get_info(interaction: discord.Interaction, index: int) -> None:
        return

    @app_commands.command(
        name="multi-pollinate", description="Imagine multiple prompts"
    )
    @app_commands.checks.cooldown(1, 20)
    @app_commands.guild_only()
    @app_commands.describe(
        prompt="Prompt of the Image you want want to generate",
        height="Height of the Image",
        width="Width of the Image",
        enhance="Enables AI Prompt Enhancement",
        negative="The things not to include in the Image",
        cached="Uses the Default seed",
        nologo="Remove the Logo",
        private="Only you can see the generated Image if set to True",
    )
    async def multiimagine_command(
        self,
        interaction: discord.Interaction,
        prompt: str,
        width: int = 1000,
        height: int = 1000,
        enhance: bool | None = None,
        negative: str | None = None,
        cached: bool = False,
        nologo: bool = False,
        private: bool = False,
    ) -> None:
        validate_dimensions(width, height)
        validate_prompt(prompt)

        total_models: int = len(MODELS)

        await interaction.response.send_message(
            embed=discord.Embed(
                title="Generating Image",
                description=f"Generating images across {total_models} models...\n"
                f"Completed: 0/{total_models} 0%",
                color=discord.Color.blurple(),
            ),
            ephemeral=private,
        )

        response: discord.InteractionMessage = await interaction.original_response()
        start_time: datetime.datetime = datetime.datetime.now()

        command_args = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "enhance": enhance,
            "negative": negative,
            "cached": cached,
            "nologo": nologo,
            "private": private,
        }

        completed_count = 0
        progress_lock = asyncio.Lock()

        async def update_progress() -> None:
            nonlocal completed_count
            async with progress_lock:
                completed_count += 1
                await response.edit(
                    embed=discord.Embed(
                        title="Generating Images",
                        description=f"Generating images across {total_models} models...\n"
                        f"Completed: {completed_count}/{total_models} "
                        f"({(completed_count / total_models * 100):.2f}%)",
                        color=discord.Color.blurple(),
                    )
                )

        async def generate_for_model(i, model):
            """Asynchronous function to generate an image for a specific model."""
            try:
                sub_start_time: datetime.datetime = datetime.datetime.now()
                dic, image = await generate_image(model=model, **command_args)
                time_taken_seconds: float = round(
                    (datetime.datetime.now() - sub_start_time).total_seconds(), 2
                )
                image_file = discord.File(image, f"image_{i}.png")
                embed: discord.Embed = discord.Embed().set_image(
                    url=f"attachment://image_{i}.png"
                )

                await update_progress()
                return (i, dic["url"], image_file, embed, time_taken_seconds, None)
            except Exception as e:
                await update_progress()
                raise ImageGenerationError(
                    f"Failed to generate image for model {model}", model_index=i
                ) from e

        try:
            results = await asyncio.wait_for(
                asyncio.gather(
                    *[generate_for_model(i, model) for i, model in enumerate(MODELS)],
                    return_exceptions=True,
                ),
                timeout=180,
            )
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError

        image_urls, embeds, files = [], [], []
        errors = []

        for result in results:
            if isinstance(result, Exception):
                if isinstance(result, ImageGenerationError):
                    errors.append(f"Model {result.model_index}: {str(result)}")
                else:
                    errors.append(str(result))
                continue

            i, url, image_file, embed, time_taken, _ = result
            image_urls.append(url)
            files.append(image_file)
            embeds.append(embed)

        if errors:
            print(errors)

        if not embeds:
            raise NoImagesGeneratedError(
                "\n".join(errors) if errors else "No images were generated"
            )

        for i in range(len(embeds)):
            embeds[i].url = image_urls[0]

        time_taken: datetime.timedelta = datetime.datetime.now() - start_time

        embeds[0].add_field(name="Prompt", value=f"```{prompt}```", inline=False)
        embeds[0].add_field(
            name="Total Time Taken", value=f"```{time_taken.total_seconds():.2f}s```"
        )

        embeds[0].set_footer(text=f"Generated by {interaction.user}")

        if private:
            await interaction.followup.send(embeds=embeds, files=files, ephemeral=True)
        else:
            await response.edit(embeds=embeds, attachments=files)

    @multiimagine_command.error
    async def multiimagine_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        """Centralized error handler for the multiimagine command."""

        if isinstance(error, app_commands.CommandOnCooldown):
            embed: discord.Embed = await generate_error_message(
                interaction,
                error,
                cooldown_configuration=["- 1 time every 20 seconds"],
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        elif isinstance(error, asyncio.TimeoutError):
            await send_error_embed(
                interaction,
                "Timeout Error",
                "Image generation took too long and timed out. Please try again.",
            )

        elif isinstance(error, NoImagesGeneratedError):
            await send_error_embed(
                interaction,
                "Generation Failed",
                f"Failed to generate any images:\n```\n{str(error)}\n```",
            )

        elif isinstance(error, PromptTooLongError):
            await send_error_embed(
                interaction,
                "Prompt Too Long",
                f"```\n{str(error)}\n```",
            )

        elif isinstance(error, APIError):
            await send_error_embed(
                interaction,
                "Couldn't Generate the Requested Image 😔",
                f"```\n{str(error)}\n```",
            )

        elif isinstance(error, DimensionTooSmallError):
            await send_error_embed(
                interaction,
                "Dimensions Too Small",
                f"```\n{str(error)}\n```",
            )

        else:
            await send_error_embed(
                interaction, "An unexprected error occurred", f"```\n{str(error)}\n```"
            )


async def setup(bot) -> None:
    await bot.add_cog(Multi_pollinate(bot))
    print("Multi-Imagine cog loaded")
