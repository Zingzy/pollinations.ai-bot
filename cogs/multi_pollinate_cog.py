import datetime
import discord
from discord import app_commands
from discord.ext import commands
import asyncio

from config import config
from utils.embed_utils import SafeEmbed
from utils.image_gen_utils import generate_image, validate_dimensions, validate_prompt
from views.multi_pollinate_view import MultiPollinateView
from cogs.base_command_cog import BaseCommandCog
from exceptions import (
    NoImagesGeneratedError,
    ImageGenerationError,
)


class Multi_pollinate(BaseCommandCog):
    """Refactored multi-pollinate command using the new architecture."""

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(
            bot, "multi_pollinate"
        )  # Automatically loads config.commands.multi_pollinate

    async def cog_load(self) -> None:
        """Setup the cog with the multi-pollinate view."""
        await super().cog_load()  # Handles common setup + logging
        self.bot.add_view(MultiPollinateView())

    def get_view_class(self):
        """Return the view class for this command."""
        return MultiPollinateView

    @app_commands.command(
        name="multi-pollinate", description="Imagine multiple prompts"
    )
    @app_commands.checks.cooldown(
        config.commands["multi_pollinate"].cooldown.rate,
        config.commands["multi_pollinate"].cooldown.seconds,
    )
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
        width: int = config.commands["multi_pollinate"].default_width,
        height: int = config.commands["multi_pollinate"].default_height,
        enhance: bool | None = config.image_generation.defaults.enhance,
        negative: str | None = None,
        cached: bool = config.image_generation.defaults.cached,
        nologo: bool = config.image_generation.defaults.nologo,
        private: bool = config.image_generation.defaults.private,
    ) -> None:
        # Validation
        validate_dimensions(width, height)
        validate_prompt(prompt)

        total_models: int = len(config.MODELS)

        if total_models == 0:
            await interaction.response.send_message(
                embed=SafeEmbed(
                    title="No Models Available",
                    description="No AI models are currently available for multi-pollination.",
                    color=int(config.ui.colors.error, 16),
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=SafeEmbed(
                title="Generating Images",
                description=f"Generating images across {total_models} models...\n"
                f"Completed: 0/{total_models} 0%",
                color=int(config.ui.colors.success, 16),
            ),
            ephemeral=private,
        )

        response: discord.InteractionMessage = await interaction.original_response()
        start_time: datetime.datetime = datetime.datetime.now()

        # Log generation start
        self.log_generation_start(
            model="multi-model",
            dimensions={"width": width, "height": height},
            cached=cached,
            action="multi_generate",
        )

        # Use MultiImageRequestBuilder for consistent parameter handling
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
                    embed=SafeEmbed(
                        title="Generating Images",
                        description=f"Generating images across {total_models} models...\n"
                        f"Completed: {completed_count}/{total_models} "
                        f"({(completed_count / total_models * 100):.2f}%)",
                        color=int(config.ui.colors.success, 16),
                    )
                )

        async def generate_for_model(i, model):
            try:
                sub_start_time: datetime.datetime = datetime.datetime.now()
                dic, image = await generate_image(model=model, **command_args)
                time_taken_seconds: float = round(
                    (datetime.datetime.now() - sub_start_time).total_seconds(), 2
                )
                image_file = discord.File(image, f"image_{i}.png")
                embed: SafeEmbed = SafeEmbed()
                embed.set_image(url=f"attachment://image_{i}.png")

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
                    *[
                        generate_for_model(i, model)
                        for i, model in enumerate(config.MODELS)
                    ],
                    return_exceptions=True,
                ),
                timeout=self.command_config.timeout_seconds,
            )
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError("Multi-pollination timed out")

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
            print(f"Multi-pollinate errors: {errors}")

        if not embeds:
            raise NoImagesGeneratedError(
                "\n".join(errors) if errors else "No images were generated"
            )

        # Set the first image URL for all embeds (for consistency)
        for i in range(len(embeds)):
            embeds[i].url = image_urls[0] if image_urls else ""

        time_taken: datetime.timedelta = datetime.datetime.now() - start_time

        # Log completion
        self.log_generation_complete(
            model="multi-model",
            dimensions={"width": width, "height": height},
            generation_time=time_taken.total_seconds(),
            cached=cached,
            action="multi_generate",
        )

        # Add metadata to first embed
        embeds[0].add_field(name="Prompt", value=f"```{prompt}```", inline=False)
        embeds[0].add_field(
            name="Total Processing Time",
            value=f"```{time_taken.total_seconds():.2f}s```",
        )
        embeds[0].add_field(
            name="Models Used",
            value=f"```{len(embeds)} models```",
            inline=True,
        )
        embeds[0].add_field(
            name="Dimensions", value=f"```{width}x{height}```", inline=True
        )

        embeds[0].set_user_footer(interaction, "Generated by")

        # Send response using base class method
        if private:
            await interaction.followup.send(embeds=embeds, files=files, ephemeral=True)
        else:
            # For multi-pollinate, we need to edit the response with the grid
            view = MultiPollinateView(image_count=len(embeds))
            await response.edit(embeds=embeds, attachments=files, view=view)

    @multiimagine_command.error
    async def multiimagine_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        """Handle command errors using centralized error handling."""
        # Handle timeout specially for multi-pollinate
        if isinstance(error, asyncio.TimeoutError):
            from utils.error_handler import send_error_embed

            await send_error_embed(
                interaction,
                "Timeout Error",
                config.ui.error_messages.get("timeout", "Operation timed out"),
                delete_after_minutes=2,
            )
        else:
            await self.handle_command_error(
                interaction,
                error,
                prompt=getattr(interaction.namespace, "prompt", "unknown"),
                width=getattr(interaction.namespace, "width", 0),
                height=getattr(interaction.namespace, "height", 0),
            )


async def setup(bot) -> None:
    """Setup function for the cog."""
    await bot.add_cog(Multi_pollinate(bot))
