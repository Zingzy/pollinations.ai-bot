import datetime
import discord
from discord import app_commands
from discord.ext import commands

from config import config
from utils.image_gen_utils import generate_cross_pollinate
from utils.embed_utils import SafeEmbed
from views.cross_pollinate_view import CrossPollinateView
from cogs.base_command_cog import BaseCommandCog


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


class CrossPollinate(BaseCommandCog):
    """Refactored cross-pollinate command using the new architecture."""

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(
            bot, "cross-pollinate"
        )  # Automatically loads config.commands.cross-pollinate

    async def cog_load(self) -> None:
        """Setup the cog with the cross-pollinate view."""
        await super().cog_load()  # Handles common setup + logging
        self.bot.add_view(CrossPollinateView())

    def get_view_class(self):
        """Return the view class for this command."""
        return CrossPollinateView

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
                    description="Please upload a valid image file (PNG, JPG, JPEG, GIF, etc.)",
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
                    description="The gptimage model is currently not available for cross-pollination. Please try again later.",
                    color=int(config.ui.colors.warning, 16),
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True, ephemeral=private)

        # Log generation start
        start = datetime.datetime.now()
        self.log_generation_start(
            model="gptimage",
            dimensions={
                "width": 0,
                "height": 0,
            },  # Cross-pollination doesn't have fixed dimensions
            cached=False,
            action="cross_pollinate",
        )

        try:
            # Generate cross-pollinated image using new utility
            dic, cross_pollinated_image = await generate_cross_pollinate(
                prompt=prompt, image_url=image.url, nologo=nologo
            )

            # Log completion
            time_taken = (datetime.datetime.now() - start).total_seconds()
            self.log_generation_complete(
                model="gptimage",
                dimensions={"width": 0, "height": 0},
                generation_time=time_taken,
                cached=False,
                action="cross_pollinate",
            )

            # Prepare response
            image_file = discord.File(
                cross_pollinated_image, filename="cross_pollinated.png"
            )
            if dic.get("nsfw", False):
                image_file.filename = f"SPOILER_{image_file.filename}"

            time_taken_delta = datetime.datetime.now() - start
            embed = await generate_cross_pollinate_embed(
                interaction,
                private,
                dic,
                time_taken_delta,
                prompt,
                image.url,
                image_file.filename,
            )

            # Send response using base class method
            if private:
                await self.send_response(interaction, embed, ephemeral=True)
            else:
                await self.send_response(interaction, embed, file=image_file)

        except Exception:
            # All error handling is automatically handled by base class
            raise

    @cross_pollinate_command.error
    async def cross_pollinate_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        """Handle command errors using centralized error handling."""
        await self.handle_command_error(
            interaction,
            error,
            prompt=getattr(interaction.namespace, "prompt", "unknown"),
            image_url=getattr(interaction.namespace, "image", {}).get("url", "unknown")
            if hasattr(getattr(interaction.namespace, "image", None), "get")
            else "unknown",
        )


async def setup(bot) -> None:
    """Setup function for the cog."""
    await bot.add_cog(CrossPollinate(bot))
