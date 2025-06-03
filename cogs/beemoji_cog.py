import datetime
import discord
from discord import app_commands
from discord.ext import commands
import traceback
import aiohttp
import re
import io
from urllib.parse import quote
from PIL import Image
import asyncio

from config import config
from utils.embed_utils import SafeEmbed, generate_error_message
from utils.error_handler import send_error_embed
from utils.logger import discord_logger
from exceptions import APIError

# Import cross-pollinate functionality for edit button
from cogs.cross_pollinate_cog import EditImageModal


class BeemojiButtonView(discord.ui.View):
    def __init__(
        self, emoji1_name: str, emoji2_name: str, generated_name: str = None
    ) -> None:
        super().__init__(timeout=None)
        self.emoji1_name = emoji1_name
        self.emoji2_name = emoji2_name
        self.generated_name = generated_name

    async def reduce_image_size(
        self, image_data: bytes, width: int, height: int
    ) -> bytes:
        """Reduce the size of the image to the given width and height"""
        loop = asyncio.get_event_loop()
        image = await loop.run_in_executor(None, Image.open, io.BytesIO(image_data))
        image = await loop.run_in_executor(
            None, lambda: image.resize((width, height), Image.Resampling.LANCZOS)
        )
        buffer = io.BytesIO()
        await loop.run_in_executor(None, lambda: image.save(buffer, format="PNG"))
        return buffer.getvalue()

    @discord.ui.button(
        label="Edit",
        style=discord.ButtonStyle.secondary,
        custom_id="beemoji-edit-button",
        emoji=f"<:edit:{config.bot.emojis['edit_emoji_id']}>",
    )
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Check if gptimage model is available
            if "gptimage" not in config.MODELS:
                await send_error_embed(
                    interaction,
                    "🎨 Model Unavailable",
                    "The gptimage model is currently not available for editing. Please try again later.",
                    delete_after_minutes=2,
                )
                return

            # Get the original image URL from the message embed
            if (
                not interaction.message.embeds
                or not interaction.message.embeds[0].thumbnail
            ):
                await send_error_embed(
                    interaction,
                    "🎨 No Image Found",
                    "Could not find the original emoji to edit.",
                    delete_after_minutes=1,
                )
                return

            original_image_url = interaction.message.embeds[0].thumbnail.url
            original_prompt = (
                f"A remixed version of {self.emoji1_name} and {self.emoji2_name} emojis"
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
            await send_error_embed(
                interaction,
                "🎨 Error Opening Edit Dialog",
                f"```\n{str(e)}\n```",
                delete_after_minutes=2,
            )

    @discord.ui.button(
        label="Add to Server",
        style=discord.ButtonStyle.primary,
        custom_id="beemoji-add-button",
        emoji="🔗",
    )
    async def add_to_server(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        try:
            # Check if user has manage emojis permission
            if not interaction.user.guild_permissions.manage_emojis:
                await send_error_embed(
                    interaction,
                    "❌ Insufficient Permissions",
                    "You need the 'Manage Emojis and Stickers' permission to add emojis to this server.",
                    delete_after_minutes=1,
                )
                return

            # Get the image URL from the embed thumbnail
            if (
                not interaction.message.embeds
                or not interaction.message.embeds[0].thumbnail
            ):
                await send_error_embed(
                    interaction,
                    "❌ No Image Found",
                    "Could not find the emoji image to add to server.",
                    delete_after_minutes=1,
                )
                return

            image_url = interaction.message.embeds[0].thumbnail.url

            await interaction.response.defer(thinking=True, ephemeral=True)

            # Download the image
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status != 200:
                        raise Exception(
                            f"Failed to download image: HTTP {response.status}"
                        )

                    image_data = await response.read()
                    # reduce the size of the image to 80x80 pixels
                    image_data = await self.reduce_image_size(image_data, 80, 80)

            emoji_name = (
                interaction.message.embeds[0].fields[1].value.split("```")[1].strip()
            )

            if not emoji_name:
                emoji_name = self.generated_name

            # Add emoji to server
            emoji = await interaction.guild.create_custom_emoji(
                name=emoji_name,
                image=image_data,
                reason=f"Beemoji created by {interaction.user}",
            )

            # disable the add to server button
            button.disabled = True
            await interaction.message.edit(view=self)

            discord_logger.log_bot_event(
                action="beemoji_add_to_server",
                status="success",
                details={
                    "user_id": interaction.user.id,
                    "guild_id": interaction.guild_id,
                    "emoji_name": emoji_name,
                },
            )

            await interaction.followup.send(
                embed=SafeEmbed(
                    title="✅ Emoji Added Successfully!",
                    description=f"The beemoji has been added to the server as {emoji} `:{emoji_name}:`",
                    color=int(config.ui.colors.success, 16),
                ),
                ephemeral=True,
            )

        except discord.HTTPException as e:
            error_message = "Failed to add emoji to server."
            if e.code == 30008:
                error_message = "The server has reached the maximum number of emojis."
            elif e.code == 50035:
                error_message = "Invalid emoji name or the name is already taken."

            discord_logger.log_error(
                error_type="emoji_add_error",
                error_message=str(e),
                context={
                    "user_id": interaction.user.id,
                    "guild_id": interaction.guild_id,
                    "error_code": getattr(e, "code", None),
                },
            )

            await send_error_embed(
                interaction,
                "❌ Failed to Add Emoji",
                f"```\n{error_message}\n```",
                delete_after_minutes=2,
            )
        except Exception as e:
            discord_logger.log_error(
                error_type="add_emoji_error",
                error_message=str(e),
                traceback=traceback.format_exc(),
                context={
                    "user_id": interaction.user.id,
                    "guild_id": interaction.guild_id if interaction.guild else None,
                },
            )
            await send_error_embed(
                interaction,
                "❌ Error Adding Emoji",
                f"```\n{str(e)}\n```",
                delete_after_minutes=2,
            )

    @discord.ui.button(
        style=discord.ButtonStyle.red,
        custom_id="beemoji-delete-button",
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
                await send_error_embed(
                    interaction,
                    "Error",
                    config.ui.error_messages["delete_unauthorized"],
                    delete_after_minutes=1,
                )
                return

            await interaction.message.delete()
            discord_logger.log_bot_event(
                action="beemoji_delete",
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
            await send_error_embed(
                interaction,
                "Error Deleting the Beemoji",
                f"```\n{str(e)}\n```",
                delete_after_minutes=2,
            )
            return


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
        name="Dimensions",
        value="```80x80```",
        inline=True,
    )

    # Set the image as thumbnail (on the side) instead of main image
    embed.set_thumbnail(url=f"attachment://{file_name}")

    embed.set_user_footer(interaction, "🐝 Beemoji created by")

    return embed


class Beemoji(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await self.bot.wait_until_ready()
        self.bot.add_view(BeemojiButtonView("", "", ""))  # Add persistent view
        discord_logger.log_bot_event(
            action="cog_load", status="success", details={"cog": "Beemoji"}
        )

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
        try:
            # Check if gptimage model is available
            if "gptimage" not in config.MODELS:
                await send_error_embed(
                    interaction,
                    "🎨 Model Unavailable",
                    "The gptimage model is currently not available. Please try again later.",
                    delete_after_minutes=2,
                )
                return

            await interaction.response.defer(thinking=True, ephemeral=private)

            # Parse emoji inputs
            try:
                emoji1_name, emoji1_url = parse_emoji_input(emoji1)
                emoji2_name, emoji2_url = parse_emoji_input(emoji2)

                # Log if we're using animated emojis
                if "_animated" in emoji1_name or "_animated" in emoji2_name:
                    discord_logger.log_bot_event(
                        action="beemoji_animated_emoji_used",
                        status="info",
                        details={
                            "user_id": interaction.user.id,
                            "emoji1": emoji1_name,
                            "emoji2": emoji2_name,
                        },
                    )

            except ValueError as e:
                await send_error_embed(
                    interaction,
                    "❌ Invalid Emoji Input",
                    f"```\n{str(e)}\n```\n\nPlease provide valid emojis. You can use:\n• Unicode emojis: 😀 🎉 ❤️\n• Custom Discord emojis: :custom_emoji: or <:name:id>\n• Animated Discord emojis: <a:name:id>\n• Emoji IDs: 123456789\n\n**Note:** Animated emojis will be converted to static images for remixing.",
                    delete_after_minutes=1,
                )
                return

            start = datetime.datetime.now()
            discord_logger.log_image_generation(
                action="beemoji_start",
                model="gptimage",
                dimensions={"width": 80, "height": 80},
                generation_time=0,
                status="started",
                cached=False,
            )

            # Generate the beemoji
            dic, beemoji_image = await generate_beemoji(
                emoji1_url, emoji2_url, emoji1_name, emoji2_name
            )

            # Generate a creative name for the emoji
            generated_emoji_name = await generate_emoji_name(emoji1_name, emoji2_name)

            time_taken = (datetime.datetime.now() - start).total_seconds()
            discord_logger.log_image_generation(
                action="beemoji_complete",
                model="gptimage",
                dimensions={"width": 80, "height": 80},
                generation_time=time_taken,
                status="success",
                cached=False,
            )

            # Create the file attachment
            image_file = discord.File(beemoji_image, filename="beemoji.png")

            time_taken_delta = datetime.datetime.now() - start
            embed = await generate_beemoji_embed(
                interaction,
                dic,
                time_taken_delta,
                emoji1,
                emoji2,
                image_file.filename,
                generated_emoji_name,
            )

            if private:
                await interaction.followup.send(
                    embed=embed, file=image_file, ephemeral=True
                )
            else:
                # Use BeemojiButtonView for public images to get edit and add to server functionality
                view = BeemojiButtonView(emoji1_name, emoji2_name, generated_emoji_name)
                await interaction.followup.send(embed=embed, view=view, file=image_file)

        except APIError as e:
            discord_logger.log_error(
                error_type="api_error",
                error_message=str(e),
                context={"command": "beemoji"},
            )
            await send_error_embed(
                interaction,
                "🐝 Couldn't Generate Beemoji 😔",
                f"```\n{str(e)}\n```",
                delete_after_minutes=2,
            )
        except Exception as e:
            discord_logger.log_error(
                error_type="beemoji_error",
                error_message=str(e),
                traceback=traceback.format_exc(),
                context={
                    "command": "beemoji",
                    "user_id": interaction.user.id,
                    "guild_id": interaction.guild_id if interaction.guild else None,
                },
            )
            await send_error_embed(
                interaction,
                "🐝 Error Generating Beemoji",
                f"```\n{str(e)}\n```",
                delete_after_minutes=2,
            )

    @beemoji_command.error
    async def beemoji_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CommandOnCooldown):
            discord_logger.log_error(
                error_type="cooldown",
                error_message=str(error),
                context={
                    "command": "beemoji",
                    "user_id": interaction.user.id,
                    "retry_after": error.retry_after,
                },
            )

            end_time = datetime.datetime.now() + datetime.timedelta(
                seconds=error.retry_after
            )
            end_time_ts = int(end_time.timestamp())

            embed = SafeEmbed(
                title="⏳ Beemoji Cooldown",
                description=f"### You can use the beemoji command again <t:{end_time_ts}:R>",
                color=int(config.ui.colors.error, 16),
                timestamp=interaction.created_at,
            )

            embed.add_field(
                name="How many times can I use this command?",
                value="- 1 time every 30 seconds",
                inline=False,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            discord_logger.log_error(
                error_type="unexpected_error",
                error_message=str(error),
                traceback=traceback.format_exception_only(type(error), error),
                context={"command": "beemoji", "user_id": interaction.user.id},
            )
            await send_error_embed(
                interaction,
                "🐝 An unexpected error occurred",
                f"```\n{str(error)}\n```",
                delete_after_minutes=2,
            )


async def setup(bot) -> None:
    await bot.add_cog(Beemoji(bot))
    discord_logger.log_bot_event(
        action="cog_setup", status="success", details={"cog": "Beemoji"}
    )
