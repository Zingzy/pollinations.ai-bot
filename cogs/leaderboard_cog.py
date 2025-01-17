import datetime
from discord import app_commands
from discord.ext import commands
import discord
from utils import generate_global_leaderboard, NUMBER_EMOJIES


class leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="leaderboard", description="Shows the leaderboard of the server"
    )
    @app_commands.guild_only()
    async def leaderboard_command(self, interaction):
        await interaction.response.defer()

        leaderboard = generate_global_leaderboard()

        leaderboard_ = {}

        for i in list(leaderboard.keys())[1:]:
            user = await self.bot.fetch_user(i)
            leaderboard_[i] = {"name": user.name, "points": leaderboard[i]}

        top_user = await self.bot.fetch_user(list(leaderboard.keys())[0])
        top_user_id = top_user.id

        try:
            top_user_avatar = top_user.avatar.url
        except Exception:
            top_user_avatar = top_user.default_avatar.url

        embed = discord.Embed(
            title="🏆 Top 10 Prompters 🏆",
            color=discord.Color.gold(),
            description="This shows the top 10 bot users across all of the servers the bot is in.",
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        embed.set_thumbnail(url=top_user_avatar)

        embed.add_field(
            name=f"{NUMBER_EMOJIES[1]}  {top_user.name} - {leaderboard[top_user_id]:,} points",
            value="** **",
            inline=False,
        )

        for i, user in enumerate(leaderboard_):
            embed.add_field(
                name=f"{NUMBER_EMOJIES[i+2]}  {leaderboard_[user]['name']} - {leaderboard_[user]['points']:,} points",
                value="** **",
                inline=False,
            )

        try:
            embed.set_footer(
                text=f"Requested by {interaction.user.name}",
                icon_url=interaction.user.avatar.url,
            )
        except Exception:
            embed.set_footer(
                text=f"Requested by {interaction.user.name}",
                icon_url=interaction.user.default_avatar.url,
            )

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(leaderboard(bot))
    print("leaderboard cog loaded")
