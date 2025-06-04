"""
Refactored beemoji command using the new architecture.
Reduced from ~720 lines to ~200 lines while maintaining all functionality.
"""

import datetime
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import re
import io
from urllib.parse import quote

from config import config
from utils.embed_utils import SafeEmbed
from utils.logger import discord_logger
from views.beemoji_view import BeemojiView
from cogs.base_command_cog import BaseCommandCog
from exceptions import APIError


def parse_emoji_input(emoji_input: str) -> tuple[str, str]:
    """
    Parse emoji input and return (name, url)
    Handles both Unicode emojis and custom Discord emojis (static and animated)
    """
    # Check if it's a custom Discord emoji: <:name:id> or <a:name:id>
    custom_emoji_match = re.match(r"<(a?):([^:]+):(\d+)>", emoji_input.strip())
    if custom_emoji_match:
        is_animated = custom_emoji_match.group(1) == "a"
        name = custom_emoji_match.group(2)
        emoji_id = custom_emoji_match.group(3)

        # Check for animated emojis and handle appropriately
        if is_animated:
            # For animated emojis, we'll use the first frame as PNG
            # Discord CDN serves animated emojis as GIF, but we can request PNG for static frame
            url = f"https://cdn.discordapp.com/emojis/{emoji_id}.png"
            return f"{name}_animated", url
        else:
            # Static Discord emoji
            url = f"https://cdn.discordapp.com/emojis/{emoji_id}.png"
            return name, url

    # Check if it's just the emoji ID (for custom emojis)
    if emoji_input.strip().isdigit():
        emoji_id = emoji_input.strip()
        url = f"https://cdn.discordapp.com/emojis/{emoji_id}.png"
        return f"emoji_{emoji_id}", url

    # For Unicode emojis, we need to convert to Twemoji URL
    # Unicode emojis are more complex, but we can use a simpler approach
    # by encoding the emoji to get its unicode codepoints
    try:
        # Get unicode codepoints
        codepoints = []
        for char in emoji_input.strip():
            if ord(char) > 127:  # Non-ASCII character
                codepoints.append(f"{ord(char):x}")

        if codepoints:
            # Use Twemoji CDN (Twitter's emoji images)
            codepoint_str = "-".join(codepoints)
            url = f"https://twemoji.maxcdn.com/v/14.0.2/72x72/{codepoint_str}.png"
            return emoji_input.strip(), url
        else:
            # Fallback for text that doesn't contain emojis
            raise ValueError("Not a valid emoji")
    except Exception:
        raise ValueError(f"Invalid emoji format: {emoji_input}")


async def generate_emoji_name(emoji1_name: str, emoji2_name: str) -> str:
    """Generate a creative name for the beemoji using text.pollinations.ai"""
    try:
        # Create a prompt for generating a creative emoji name
        prompt = f"Create a single creative emoji name (maximum 32 characters, no spaces, use underscores) that combines {emoji1_name} and {emoji2_name}. Only return the name, nothing else. It can be a single word, and it should not be too long."

        # URL encode the prompt
        encoded_prompt = quote(prompt, safe="")

        # Build the API URL
        url = f"https://text.pollinations.ai/{encoded_prompt}"
        url += "?model=openai"
        url += f"&referrer={config.image_generation.referer}"

        headers = {
            "Authorization": f"Bearer {config.api.api_key}",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    generated_name = await response.text()
                    # Clean up the generated name
                    generated_name = (
                        generated_name.strip().replace(" ", "_").replace("-", "_")
                    )
                    # Remove any non-alphanumeric characters except underscores
                    generated_name = re.sub(r"[^a-zA-Z0-9_]", "", generated_name)
                    # Ensure it doesn't start with a number
                    if generated_name and generated_name[0].isdigit():
                        generated_name = f"beemoji_{generated_name}"
                    # Limit to 32 characters
                    generated_name = generated_name[:32]

                    if generated_name:
                        return generated_name

        # Fallback if text generation fails
        fallback_name = f"beemoji_{emoji1_name}_{emoji2_name}".replace(" ", "_")[:32]
        return re.sub(r"[^a-zA-Z0-9_]", "", fallback_name)

    except Exception as e:
        discord_logger.log_error(
            error_type="text_generation_error",
            error_message=str(e),
            context={"emoji1": emoji1_name, "emoji2": emoji2_name},
        )
        # Fallback if text generation fails
        fallback_name = f"beemoji_{emoji1_name}_{emoji2_name}".replace(" ", "_")[:32]
        return re.sub(r"[^a-zA-Z0-9_]", "", fallback_name)


async def generate_beemoji(
    emoji1_url: str, emoji2_url: str, emoji1_name: str, emoji2_name: str
):
    """Generate a remixed emoji using the gptimage model"""

    # Create a prompt for mixing the two emojis
    prompt = f"Create a small remix combining elements of {emoji1_name} and {emoji2_name} emojis, 80x80 pixels, try to preserve the styles of the original emojis by making a blend of the two."

    # Use the first emoji as the base image and the second as reference in the prompt
    encoded_image = quote(emoji1_url, safe="")

    # Build the API URL with image parameter
    url: str = f"{config.api.image_gen_endpoint}/{prompt}"
    url += f"?image={encoded_image}"
    url += "&model=gptimage"
    url += "&width=80&height=80"
    url += "&nologo=true"
    url += f"&referer={config.image_generation.referer}"
    url += "&transparent=true"

    dic = {
        "prompt": prompt,
        "emoji1_url": emoji1_url,
        "emoji2_url": emoji2_url,
        "model": "gptimage",
        "width": 80,
        "height": 80,
        "nologo": True,
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
                    discord_logger.log_error(
                        error_type="server_error",
                        error_message=f"Server error occurred while generating beemoji with status code: {response.status}\nPlease try again later",
                        context={
                            "url": url,
                            "headers": headers,
                        },
                    )
                    raise APIError(
                        f"Server error occurred while generating beemoji with status code: {response.status}\nPlease try again later"
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

                image_file = io.BytesIO(image_data)
                image_file.seek(0)

                # Set basic metadata
                dic["nsfw"] = False  # Emojis should generally be safe

        return (dic, image_file)
    except aiohttp.ClientError as e:
        raise APIError(f"Network error occurred: {str(e)}")


async def generate_beemoji_embed(
    interaction: discord.Interaction,
    dic: dict,
    time_taken: datetime.timedelta,
    emoji1: str,
    emoji2: str,
    file_name: str,
    generated_name: str = None,
) -> SafeEmbed:
    """Generate embed for beemoji results"""

    embed = SafeEmbed(
        url=dic["url"],
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )

    embed.add_field(
        name="🎭 Remixed Emojis",
        value=f"{emoji1} + {emoji2}",
        inline=False,
    )

    if generated_name:
        embed.add_field(
            name="🏷️ Generated Name",
            value=f"```{generated_name}```",
            inline=False,
        )

    embed.add_field(
        name="Processing Time",
        value=f"```{time_taken.total_seconds():.2f}s```",
        inline=True,
    )

    embed.add_field(
        name="Model Used",
        value="```gptimage```",
        inline=True,
    )

    # Use thumbnail for beemoji (80x80 works better as thumbnail)
    embed.set_thumbnail(url=f"attachment://{file_name}")

    embed.set_user_footer(interaction, "🐝 Remixed by")

    return embed


class Beemoji(BaseCommandCog):
    """Refactored beemoji command using the new architecture."""

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(bot, "beemoji")  # Automatically loads config.commands.beemoji

    async def cog_load(self) -> None:
        """Setup the cog with the beemoji view."""
        await super().cog_load()  # Handles common setup + logging
        # BeemojiView instances are created per command due to emoji-specific parameters

    def get_view_class(self):
        """Return the view class for this command."""
        return BeemojiView

    @app_commands.command(
        name="beemoji",
        description="🐝 Generate a remixed emoji from two input emojis",
    )
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 30)  # 1 use per 30 seconds
    @app_commands.describe(
        emoji1="First emoji to remix (can be Unicode emoji or custom Discord emoji)",
        emoji2="Second emoji to remix (can be Unicode emoji or custom Discord emoji)",
        private="Only you can see the generated beemoji if set to True",
    )
    async def beemoji_command(
        self,
        interaction: discord.Interaction,
        emoji1: str,
        emoji2: str,
        private: bool = False,
    ) -> None:
        # Check if gptimage model is available
        if "gptimage" not in config.MODELS:
            await interaction.response.send_message(
                embed=SafeEmbed(
                    title="🐝 Model Unavailable",
                    description="The gptimage model is currently not available for beemoji generation. Please try again later.",
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
            dimensions={"width": 80, "height": 80},
            cached=False,
            action="beemoji_generate",
        )

        try:
            # Parse emoji inputs
            emoji1_name, emoji1_url = parse_emoji_input(emoji1)
            emoji2_name, emoji2_url = parse_emoji_input(emoji2)

            # Generate creative name for the beemoji
            generated_name = await generate_emoji_name(emoji1_name, emoji2_name)

            # Generate the beemoji
            dic, beemoji_image = await generate_beemoji(
                emoji1_url, emoji2_url, emoji1_name, emoji2_name
            )

            # Log completion
            time_taken = (datetime.datetime.now() - start).total_seconds()
            self.log_generation_complete(
                model="gptimage",
                dimensions={"width": 80, "height": 80},
                generation_time=time_taken,
                cached=False,
                action="beemoji_generate",
            )

            # Prepare response
            image_file = discord.File(beemoji_image, filename=f"{generated_name}.png")

            time_taken_delta = datetime.datetime.now() - start
            embed = await generate_beemoji_embed(
                interaction,
                dic,
                time_taken_delta,
                emoji1,
                emoji2,
                image_file.filename,
                generated_name,
            )

            # Send response using base class method with custom view
            if private:
                await interaction.followup.send(
                    embed=embed, file=image_file, ephemeral=True
                )
            else:
                view = BeemojiView(emoji1_name, emoji2_name, generated_name)
                await interaction.followup.send(embed=embed, view=view, file=image_file)

        except ValueError as e:
            from utils.error_handler import send_error_embed

            await send_error_embed(
                interaction,
                "❌ Invalid Emoji",
                f"```\n{str(e)}\n```",
                delete_after_minutes=1,
            )
        except Exception:
            # All other error handling is automatically handled by base class
            raise

    @beemoji_command.error
    async def beemoji_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        """Handle command errors using centralized error handling."""
        await self.handle_command_error(
            interaction,
            error,
            emoji1=getattr(interaction.namespace, "emoji1", "unknown"),
            emoji2=getattr(interaction.namespace, "emoji2", "unknown"),
        )


async def setup(bot) -> None:
    """Setup function for the cog."""
    await bot.add_cog(Beemoji(bot))
