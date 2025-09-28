import datetime
import discord
from discord import app_commands
from discord.ext import commands

from config import config
from utils.image_gen_utils import generate_image, validate_dimensions, validate_prompt
from utils.embed_utils import generate_pollinate_embed
from views.imagine_view import ImagineView
from cogs.base_command_cog import BaseCommandCog


class Imagine(BaseCommandCog):
    """Refactored imagine command using the new architecture."""

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(
            bot, "pollinate"
        )  # Automatically loads config.commands.pollinate

    async def cog_load(self) -> None:
        """Setup the cog with the imagine view."""
        await super().cog_load()  # Handles common setup + logging
        self.bot.add_view(ImagineView())

    def get_view_class(self):
        """Return the view class for this command."""
        return ImagineView

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
        # Validation (handled by utilities)
        validate_dimensions(width, height)
        validate_prompt(prompt)

        await interaction.response.defer(thinking=True, ephemeral=private)

        # Extract model value
        model_value = model.value if hasattr(model, "value") else model

        # Log generation start
        start = datetime.datetime.now()
        self.log_generation_start(
            model=model_value or "default",
            dimensions={"width": width, "height": height},
            cached=cached,
        )

        try:
            # Generate image using new utility
            dic, image = await generate_image(
                prompt=prompt,
                width=width,
                height=height,
                model=model_value,
                safe=safe,
                cached=cached,
                nologo=nologo,
                enhance=enhance,
                private=private,
            )

            # Log completion
            time_taken = (datetime.datetime.now() - start).total_seconds()
            self.log_generation_complete(
                model=model_value or "default",
                dimensions={"width": width, "height": height},
                generation_time=time_taken,
                cached=cached,
            )

            # Prepare response
            image_file = discord.File(image, filename="image.png")
            if dic["nsfw"]:
                image_file.filename = f"SPOILER_{image_file.filename}"

            time_taken_delta = datetime.datetime.now() - start
            embed = await generate_pollinate_embed(
                interaction, private, dic, time_taken_delta
            )

            # Send response using base class method
            if private:
                await self.send_response(interaction, embed, ephemeral=True)
            else:
                await self.send_response(interaction, embed, file=image_file)

        except Exception:
            # All error handling is automatically handled by base class
            raise

    @imagine_command.error
    async def imagine_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        """Handle command errors using centralized error handling."""
        await self.handle_command_error(
            interaction,
            error,
            prompt=getattr(interaction.namespace, "prompt", "unknown"),
            model=getattr(interaction.namespace, "model", "unknown"),
            width=getattr(interaction.namespace, "width", 0),
            height=getattr(interaction.namespace, "height", 0),
        )


async def setup(bot) -> None:
    """Setup function for the cog."""
    await bot.add_cog(Imagine(bot))
