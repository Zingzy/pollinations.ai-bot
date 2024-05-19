import datetime
import discord
from discord import app_commands, ui
from discord.ext import commands
import math

from utils import *
from constants import *

class Paginator(ui.View):
    current_page = 1
    sep = 4

    def __init__(self, *, timeout: float | None = 30*60):
        super().__init__(timeout=timeout)

    async def send(self, interaction:discord.Interaction):
        await interaction.response.defer()
        embeds = self.create_embed(interaction, self.data[:self.sep])
        await self.update_buttons()
        await interaction.followup.send(embeds=embeds, view=self)

    def create_embed(self, interaction:discord.Interaction, data):

        urls = [prompts.find_one(i)["bookmark_url"] for i in data]
        prompts_ = "\n".join(["• "+prompts.find_one(i)["prompt"] for i in data])

        embeds = []
        for i in urls:
            embed = discord.Embed(url="https://polliations.ai", color=discord.Color.blurple(), timestamp=datetime.datetime.now(datetime.timezone.utc))
            embed.set_image(url=i)
            embeds.append(embed)

        try:
            embeds[0].set_author(name=f"{interaction.user.name}'s {self.typ} Images", icon_url=interaction.user.avatar.url)
        except:
            embeds[0].set_author(name=f"{interaction.user.name}'s {self.typ} Images", icon_url=interaction.user.default_avatar.url)
        embeds[0].set_footer(text=f"Page {self.current_page}/{math.ceil(len(self.data) / self.sep)}")
        embeds[0].add_field(name=f"The Prompts for the Images you {self.typ} are below.", value=f"```{prompts_}```", inline=False)

        return embeds

    async def update_message(self, interaction:discord.Interaction, data):
        await interaction.response.defer()
        await self.update_buttons()
        await interaction.edit_original_response(embeds=self.create_embed(interaction, data), view=self)

    async def update_buttons(self):
        if self.current_page == 1:
            self.first_page.disabled = True
            self.previous_page.disabled = True
        else:
            self.first_page.disabled = False
            self.previous_page.disabled = False

        if self.current_page == math.ceil(len(self.data) / self.sep):
            self.next_page.disabled = True
            self.last_page.disabled = True
        else:
            self.next_page.disabled = False
            self.last_page.disabled = False

    @ui.button(label="", style=discord.ButtonStyle.secondary, emoji="<:first:1222913712881406043>")
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 1
        until_item = self.current_page * self.sep
        from_item = until_item - self.sep

        await self.update_message(interaction, self.data[from_item:until_item])

    @ui.button(label="", style=discord.ButtonStyle.primary, emoji="<:previous:1222913715553439836>")
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        until_item = self.current_page * self.sep
        from_item = until_item - self.sep

        await self.update_message(interaction, self.data[from_item:until_item])

    @ui.button(label="", style=discord.ButtonStyle.danger, emoji="<:exit:1222913718418018446>")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=None)

    @ui.button(label="", style=discord.ButtonStyle.primary, emoji="<:next:1222913707684659320>")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        until_item = self.current_page * self.sep
        from_item = until_item - self.sep

        await self.update_message(interaction, self.data[from_item:until_item])

    @ui.button(label="", style=discord.ButtonStyle.secondary, emoji="<:last:1222913710364823693>")
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = len(self.data) // self.sep + 1
        until_item = self.current_page * self.sep
        from_item = until_item - self.sep

        await self.update_message(interaction, self.data[from_item:until_item])

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

class userInfo(commands.GroupCog, name="user"):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        await self.bot.wait_until_ready()

    @app_commands.command(
        name="info",
        description="Get information about a user",
    )
    @app_commands.describe(user="The user you want to get information about")
    @app_commands.checks.cooldown(1, 5)
    async def userinfo(self, interaction:discord.Interaction, user:discord.User = None):
        user = interaction.user if user is None else user

        embed = discord.Embed(
            color=discord.Color.blurple(),
            description="Here are some basic information about the user.",
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )

        try:
            embed.set_author(name=user.name+"'s Information", icon_url=user.avatar.url)
        except:
            embed.set_author(name=user.name+"'s Information", icon_url=user.default_avatar.url)

        user_info = users.find_one({"_id": user.id})
        if user_info is None:
            raise commands.CommandError("User not found in database")
        total_images_generated = len(user_info["prompts"])
        total_images_liked = len(user_info["likes"])
        last_prompt = user_info["last_prompt"]

        last_prompt_data = prompts.find_one({"_id": last_prompt})
        if last_prompt_data is None:
            raise commands.CommandError("Last Prompt not found in database")
        last_prompt_info = last_prompt_data["prompt"]
        last_prompt_uri = last_prompt_data["bookmark_url"]

        embed.add_field(name="Total Generations", value=f"```{total_images_generated}```", inline=True)
        embed.add_field(name="Total Likes", value=f"```{total_images_liked}```", inline=True)
        embed.add_field(name="Last Prompt", value=f"```{last_prompt_info}```", inline=False)

        embed.set_image(url=last_prompt_uri)
        embed.set_footer(text=f"Requested by {interaction.user.name}", icon_url=interaction.user.avatar.url)

        await interaction.response.send_message(embed=embed)

    @userinfo.error
    async def userinfo_error(self, interaction:discord.Interaction, error):
        if isinstance(error, commands.CommandOnCooldown):
            end_time = datetime.datetime.now() + datetime.timedelta(
                seconds=error.retry_after
            )
            end_time_str = end_time.strftime("%Y-%m-%d %H:%M:%S UTC")
            end_time_ts = f"<t:{int(end_time.timestamp())}>"

            hours, remainder = divmod(error.retry_after, 3600)
            minutes, seconds = divmod(remainder, 60)
            seconds = round(seconds)
            time_left = f"{ hours + ' hour, ' if not hours<1 else ''}{int(minutes)} minute{'s' if minutes != 1 else ''} and {seconds} second{'s' if seconds != 1 else ''}"

            embed = discord.Embed(
                title="⏳ Cooldown",
                description=f"You have to wait until **{end_time_ts}** ({time_left}) before using the </imagine:1123582901544558612> command again.",
                color=discord.Color.red(),
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="Error",
                description=f"```An error occurred: {error}```",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


    @app_commands.command(
        name="likes",
        description="See all of the images liked by you",
    )
    @app_commands.checks.cooldown(1, 10)
    async def userLikes(self, interaction:discord.Integration):
        user = interaction.user

        user_info = users.find_one({"_id": user.id})
        if user_info is None:
            raise commands.CommandError("User not found in database")

        likes = user_info["likes"]
        likes = likes[::-1]

        if likes == []:
            interaction.response.send_message(embed=discord.Embed(description="You haven't liked any images yet.", color=discord.Color.orange()), ephemeral=True)
            return

        pagination = Paginator()
        pagination.data = likes
        pagination.typ = "Liked"
        await pagination.send(interaction)


    @app_commands.command(
        name="generations",
        description="See all of the images generated by you",
    )
    @app_commands.checks.cooldown(1, 10)
    async def userGenerations(self, interaction:discord.Interaction):
        user = interaction.user

        user_info = users.find_one({"_id": user.id})
        if user_info is None:
            raise commands.CommandError("User not found in database")

        generations = user_info["prompts"]
        generations = generations[::-1]

        if generations == []:
            interaction.response.send_message(embed=discord.Embed(description="You haven't generated any images yet.", color=discord.Color.orange()), ephemeral=True)
            return

        pagination = Paginator()
        pagination.data = generations
        pagination.typ = "Generated"
        await pagination.send(interaction)


    @app_commands.command(
        name="bookmarks",
        description="See all of the images bookmarked by you",
    )
    @app_commands.checks.cooldown(1, 10)
    async def userBookmarks(self, interaction:discord.Interaction):
        user = interaction.user

        user_info = users.find_one({"_id": user.id})
        if user_info is None:
            raise commands.CommandError("User not found in database")

        bookmarks = user_info["bookmarks"]
        bookmarks = bookmarks[::-1]

        if bookmarks == []:
            interaction.response.send_message(embed=discord.Embed(description="You haven't bookmarked any images yet.", color=discord.Color.orange()), ephemeral=True)
            return

        pagination = Paginator()
        pagination.data = bookmarks
        pagination.typ = "Bookmarked"
        await pagination.send(interaction)

    @userLikes.error
    @userGenerations.error
    @userBookmarks.error
    async def userLikes_error(self, interaction:discord.Interaction, error):
        if isinstance(error, commands.CommandOnCooldown):
            end_time = datetime.datetime.now() + datetime.timedelta(
                seconds=error.retry_after
            )
            end_time_str = end_time.strftime("%Y-%m-%d %H:%M:%S UTC")
            end_time_ts = f"<t:{int(end_time.timestamp())}>"

            hours, remainder = divmod(error.retry_after, 3600)
            minutes, seconds = divmod(remainder, 60)
            seconds = round(seconds)
            time_left = f"{ hours + ' hour, ' if not hours<1 else ''}{int(minutes)} minute{'s' if minutes != 1 else ''} and {seconds} second{'s' if seconds != 1 else ''}"

            embed = discord.Embed(
                title="⏳ Cooldown",
                description=f"You have to wait until **{end_time_ts}** ({time_left}) before using the </imagine:1123582901544558612> command again.",
                color=discord.Color.red(),
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="Error",
                description=f"```An error occurred: {error}```",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(userInfo(bot))
    print("userInfo cog loaded")