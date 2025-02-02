from dotenv import load_dotenv
import os
import datetime
import discord
from discord.ext import commands, tasks
import statistics
import time
import sys
import aiohttp
from config import config

load_dotenv(override=True)

TOKEN: str = os.environ["TOKEN"]
start_time = None
latencies: list = []

commands_: dict[str, str] = {
    f"</pollinate:{config.bot.commands['pollinate_id']}> 🎨": """Generates AI Images based on your prompts
- **prompt** 🗣️ : Your prompt for the Image to be generated
- **width** ↔️ : The width of your prompted Image
- **height** ↕️ : The height of your prompted Image
- **enhance** 🖼️ : Specifies whether to enhance the image prompt or not
- **cached** : specifies whether to return a cached image
- **negative** ❎ : Specifies what not to be in the generated images
- **nologo** 🚫 : Specifies whether to remove the logo from the generated images (deafault False)
- **private** 🔒 : when set to True the generated Image will only be visible to you
""",
    f"</multi-pollinate:{config.bot.commands['multi_pollinate_id']}> 🎨": """Generates AI Images using all available models
- **prompt** 🗣️ : Your prompt for the Image to be generated
- **width** ↔️ : The width of your prompted Image
- **height** ↕️ : The height of your prompted Image
- **cached** : specifies whether to return a cached image
- **negative** ❎ : Specifies what not to be in the generated images
- **nologo** 🚫 : Specifies whether to remove the logo from the generated images (deafault False)
- **enhance** 🖼️ : Specifies whether to enhance the image prompt or not (default True)
- **private** 🔒 : when set to True the generated Image will only be visible to you
""",
    f"</random:{config.bot.commands['random_id']}> 🎨": """Generates Random AI Images
- **width** ↔️ : The width of your prompted Image
- **height** ↕️ : The height of your prompted Image
- **negative** ❎ : Specifies what not to be in the generated images
- **nologo** 🚫 : Specifies whether to remove the logo from the generated images (deafault False)
- **private** 🔒 : when set to True the generated Image will only be visible to you
""",
    f"</help:{config.bot.commands['help_id']}> ❓": "Displays this",
    f"</invite:{config.bot.commands['invite_id']}> 📨": "Invite the bot to your server",
    f"</about:{config.bot.commands['about_id']}> ℹ️": "About the bot",
}


class pollinationsBot(commands.Bot):
    def __init__(self) -> None:
        intents: discord.Intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True

        super().__init__(
            command_prefix=config.bot.command_prefix, intents=intents, help_command=None
        )
        self.synced = False

    @tasks.loop(minutes=config.api.models_refresh_interval_minutes)
    async def refresh_models(self) -> None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(config.api.models_list_endpoint) as response:
                    if response.ok:
                        config.MODELS.clear()
                        config.MODELS.extend(await response.json())
                        print(f"Models refreshed: {config.MODELS}")
        except Exception as e:
            config.MODELS = [config.image_generation.fallback_model]
            print(f"Error refreshing models: {e}", file=sys.stdout)

    async def on_ready(self) -> None:
        await load()

        global start_time
        start_time = datetime.datetime.now(datetime.UTC)

        await self.wait_until_ready()
        await bot.change_presence(
            activity=discord.CustomActivity(
                name="Custom Status",
                state="/pollinate to generate AI images",
            )
        )
        if not self.synced:
            await self.tree.sync()
            self.refresh_models.start()
            self.synced = True

        print(f"Logged in as {self.user.name} (ID: {self.user.id})")
        print(f"Connected to {len(self.guilds)} guilds")
        print(f"Available MODELS: {config.MODELS}")


bot = pollinationsBot()


async def load() -> None:
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await bot.load_extension(f"cogs.{filename[:-3]}")


@bot.event
async def on_message(message) -> None:
    if message.author == bot.user:
        return

    if bot.user in message.mentions:
        if message.type is not discord.MessageType.reply:
            embed = discord.Embed(
                description=f"Hello, I am the Pollinations.ai Bot. I am here to help you with your AI needs. **To Generate Images click </pollinate:{config.bot.commands['pollinate_id']}> or </multi-pollinate:{config.bot.commands['multi_pollinate_id']}> or type `/help` for more commands**.",
                color=int(config.ui.colors.success, 16),
            )

            await message.reply(embed=embed)

    await bot.process_commands(message)


@bot.command()
@commands.is_owner()
async def sync(ctx) -> None:
    await bot.tree.sync()
    synced = await bot.tree.sync()
    if len(synced) > 0:
        await ctx.send(f"Successfully Synced {len(synced)} Commands ✔️")
    else:
        await ctx.send("No Slash Commands to Sync :/")


@bot.event
async def on_command_completion(ctx) -> None:
    end: float = time.perf_counter()
    start: float = ctx.start
    latency: int = (end - start) * 1000
    latencies.append(latency)
    if len(latencies) > 10:
        latencies.pop(0)


@bot.before_invoke
async def before_invoke(ctx) -> None:
    start: float = time.perf_counter()
    ctx.start = start


@bot.command()
async def ping(ctx) -> None:
    try:
        embed = discord.Embed(title="Pong!", color=int(config.ui.colors.success, 16))
        message = await ctx.send(embed=embed)

        end: float = time.perf_counter()
        latency: int = (end - ctx.start) * 1000

        embed.add_field(name="Ping", value=f"{bot.latency * 1000:.2f} ms", inline=False)
        embed.add_field(name="Message Latency", value=f"{latency:.2f} ms", inline=False)

        if latencies:
            average_ping = statistics.mean(latencies)
            embed.add_field(
                name="Average Message Latency",
                value=f"{average_ping:.2f} ms",
                inline=False,
            )

        global start_time
        current_time: datetime.datetime = datetime.datetime.now(datetime.UTC)
        delta: datetime.timedelta = current_time - start_time

        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)

        embed.add_field(
            name="Uptime",
            value=f"{hours} hours {minutes} minutes {seconds} seconds",
            inline=False,
        )
        embed.set_footer(
            text=f"Information requested by: {ctx.author.name}",
            icon_url=ctx.author.avatar.url,
        )
        embed.set_thumbnail(url=config.bot_avatar_url)

        await message.edit(embed=embed)

    except Exception as e:
        print(e, file=sys.stdout)


@bot.hybrid_command(name="help", description="View the various commands of this server")
async def help(ctx) -> None:
    user: discord.User | None = bot.get_user(int(config.bot.bot_id))
    try:
        profilePicture: str = user.avatar.url
    except AttributeError:
        profilePicture = config.bot.avatar_url

    embed = discord.Embed(
        title="Pollinations.ai Bot Commands",
        description="Here is the list of the available commands:",
        color=int(config.ui.colors.success, 16),
    )

    embed.set_thumbnail(url=profilePicture)
    for i in commands_.keys():
        embed.add_field(name=i, value=commands_[i], inline=False)

    embed.set_footer(
        text=f"Information requested by: {ctx.author.name}",
        icon_url=ctx.author.avatar.url,
    )

    await ctx.send(embed=embed)


@bot.hybrid_command(name="invite", description="Invite the bot to your server")
async def invite(ctx) -> None:
    embed = discord.Embed(
        title="Invite the bot to your server",
        url=config.ui.bot_invite_url,
        description="Click the link above to invite the bot to your server",
        color=int(config.ui.colors.success, 16),
    )

    embed.set_footer(
        text=f"Information requested by: {ctx.author.name}",
        icon_url=ctx.author.avatar.url,
    )

    await ctx.send(embed=embed)


@bot.hybrid_command(name="about", description="About the bot")
async def about(ctx) -> None:
    user: discord.User | None = bot.get_user(int(config.bot.bot_id))
    try:
        profilePicture: str = user.avatar.url
    except AttributeError:
        profilePicture = config.bot.avatar_url

    embed = discord.Embed(
        title="About Pollinations.ai Bot 🙌",
        url=config.ui.api_provider_url,
        description="I am the official Pollinations.ai Bot. I can generate AI Images from your prompts ✨.",
        color=int(config.ui.colors.success, 16),
    )

    github_emoji: discord.Emoji | None = discord.utils.get(
        bot.emojis, id=int(config.bot.emojis["github_emoji_id"]), name="github"
    )

    embed.set_thumbnail(url=profilePicture)
    embed.add_field(
        name="What is Pollinations.ai? 🌸",
        value="Pollinations.ai is a platform for creating AI-generated images completely for free. We have a growing collection of AI models that you can use to generate images.",
        inline=False,
    )
    embed.add_field(
        name="What can I do with this bot? 🤖",
        value="You can use this bot to generate AI images using our platform.",
        inline=False,
    )
    embed.add_field(
        name="How do I use this bot? 🤔",
        value=f"You can use this bot by typing `/help` or clicking </help:{config.bot.commands['help_id']}> to get started.",
        inline=False,
    )
    embed.add_field(
        name="How do I report a bug? 🪲",
        value=f"You can report a bug by joining our [Discord Server]({config.ui.support_server_url}).",
        inline=False,
    )
    embed.add_field(
        name=f"How do I contribute to this project? {str(github_emoji)}",
        value=f"This project is open source. You can contribute to this project by visiting our [GitHub Repository]({config.ui.github_repo_url}).",
        inline=False,
    )

    embed.add_field(name="Servers", value=f"```{len(bot.guilds)}```", inline=True)

    global start_time
    current_time: datetime.datetime = datetime.datetime.now(datetime.UTC)
    delta: datetime.timedelta = current_time - start_time

    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)

    embed.add_field(
        name="Uptime",
        value=f"```{hours} hours {minutes} minutes {seconds} seconds```",
        inline=False,
    )

    embed.set_footer(
        text="Bot created by Zngzy",
        icon_url=config.ui.bot_creator_avatar,
    )

    await ctx.send(embed=embed)


if __name__ == "__main__":
    bot.run(token=TOKEN)
