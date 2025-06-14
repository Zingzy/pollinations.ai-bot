import datetime
import discord
from discord import app_commands
from discord.ext import commands

from config import config
from utils.image_gen_utils import generate_image, validate_dimensions
from utils.embed_utils import generate_error_message, SafeEmbed
from utils.error_handler import send_error_embed
from utils.logger import discord_logger
from exceptions import DimensionTooSmallError, APIError

# Import cross-pollinate button view for edit functionality
from cogs.cross_pollinate_cog import CrossPollinateButtonView


class RandomImage(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.command_config = config.commands["random"]

    async def cog_load(self) -> None:
        await self.bot.wait_until_ready()
        self.bot.add_view(CrossPollinateButtonView())
        discord_logger.log_bot_event(
            action="cog_load", status="success", details={"cog": "RandomImage"}
        )

    @app_commands.command(name="random", description="Generate Random AI Images")
    @app_commands.choices(
        model=[
            app_commands.Choice(name=choice, value=choice) for choice in config.MODELS
        ],
    )
    @app_commands.guild_only()
    @app_commands.checks.cooldown(
        config.commands["random"].cooldown.rate,
        config.commands["random"].cooldown.seconds,
    )
    @app_commands.describe(
        height="Height of the image",
        width="Width of the image",
        model="The model to use for generating the image",
        negative="The things not to include in the image",
        nologo="Remove the logo",
        private="Only you can see the generated Image if set to True",
    )
    async def random_image_command(
        self,
        interaction: discord.Interaction,
        width: int = config.commands["random"].default_width,
        height: int = config.commands["random"].default_height,
        model: app_commands.Choice[str] = config.MODELS[0],
        negative: str | None = None,
        nologo: bool = config.image_generation.defaults.nologo,
        private: bool = config.image_generation.defaults.private,
    ) -> None:
        validate_dimensions(width, height)

        await interaction.response.defer(thinking=True, ephemeral=private)

        try:
            model = model.value if model else None
        except Exception:
            pass

        start: datetime.datetime = datetime.datetime.now()

        dic, image = await generate_image(
            "Random Prompt",
            width,
            height,
            model,
            negative,
            False,
            nologo,
            True,
            private,
        )

        image_file = discord.File(image, filename="image.png")

        if dic["nsfw"]:
            image_file.filename = f"SPOILER_{image_file.filename}"

        time_taken: datetime.timedelta = datetime.datetime.now() - start

        embed = SafeEmbed(
            title="Random Prompt",
            description=f"```{dic['enhanced_prompt']}```"
            if "enhanced_prompt" in dic
            else "",
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            url=dic["url"],
        )

        embed.add_field(name="Seed", value=f"```{dic['seed']}```", inline=True)

        embed.add_field(
            name="Processing Time",
            value=f"```{round(time_taken.total_seconds(), 2)} s```",
            inline=True,
        )

        embed.set_image(url="attachment://image.png")

        if not private:
            embed.set_user_footer(interaction, "🎲 Generated by")

        if private:
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        else:
            # Use CrossPollinateButtonView for public images to get edit, delete, and bookmark functionality
            view = CrossPollinateButtonView()
            await interaction.followup.send(embed=embed, view=view, file=image_file)

    @random_image_command.error
    async def random_image_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CommandOnCooldown):
            embed: SafeEmbed = await generate_error_message(
                interaction,
                error,
                cooldown_configuration=[
                    f"- {self.command_config.cooldown.rate} time every {self.command_config.cooldown.seconds} seconds",
                ],
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        elif isinstance(error, DimensionTooSmallError):
            await send_error_embed(
                interaction,
                "Dimensions Too Small",
                f"```\n{str(error)}\n```",
                delete_after_minutes=0.5,
            )

        elif isinstance(error, APIError):
            await send_error_embed(
                interaction,
                "Couldn't Generate the Requested Image 😔",
                f"```\n{str(error)}\n```",
                delete_after_minutes=2,
            )

        else:
            await send_error_embed(
                interaction,
                config.ui.error_messages["unknown"],
                f"```\n{str(error)}\n```",
                delete_after_minutes=2,
            )


async def setup(bot) -> None:
    await bot.add_cog(RandomImage(bot))
    discord_logger.log_bot_event(
        action="cog_setup", status="success", details={"cog": "RandomImage"}
    )
