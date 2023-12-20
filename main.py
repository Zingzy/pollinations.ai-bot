from pymongo import MongoClient
from dotenv import load_dotenv
import os
import json
import requests
import datetime
import discord
from discord.ext import commands
from discord import app_commands, ui
from api import *
import statistics
import time
import sys
from constants import *
from api import *


load_dotenv()

start_time = None
latencies = []


class pollinationsBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!", intents=discord.Intents.all(), help_command=None
        )
        self.synced = False

    async def on_ready(self):
        await load()

        global start_time
        start_time = datetime.datetime.utcnow()

        await self.wait_until_ready()
        if not self.synced:
            await self.tree.sync()
            await bot.change_presence(
                activity=discord.CustomActivity(
                    name="Custom Status",
                    state=f"Converting Text to Image.",
                )
            )
            self.synced = True

        print(f"Logged in as {self.user.name} (ID: {self.user.id})")
        print(f"Connected to {len(self.guilds)} guilds")


bot = pollinationsBot()


async def load():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            await bot.load_extension(f'cogs.{filename[:-3]}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    await bot.process_commands(message)


@bot.command()
@commands.is_owner()
async def sync(ctx):
    await bot.tree.sync()
    synced = await bot.tree.sync()
    if len(synced) > 0:
        await ctx.send(f"Successfully Synced {len(synced)} Commands ✔️")
    else:
        await ctx.send("No Slash Commands to Sync :/")


@bot.event
async def on_command_completion(ctx):
    end = time.perf_counter()
    start = ctx.start
    latency = (end - start) * 1000
    latencies.append(latency)
    if len(latencies) > 10:
        latencies.pop(0)


@bot.before_invoke
async def before_invoke(ctx):
    start = time.perf_counter()
    ctx.start = start


@bot.command()
async def ping(ctx):
    try:
        embed = discord.Embed(title="Pong!", color=discord.Color.green())
        message = await ctx.send(embed=embed)

        end = time.perf_counter()

        latency = (end - ctx.start) * 1000

        embed.add_field(name="Message Latency", value=f"{latency:.2f} ms", inline=False)
        embed.add_field(
            name="Websocket Latency", value=f"{bot.latency * 1000:.2f} ms", inline=False
        )

        # Calculate the average ping of the bot in the last 10 minutes
        if latencies:
            average_ping = statistics.mean(latencies)
            embed.add_field(
                name="Average Ping", value=f"{average_ping:.2f} ms", inline=False
            )

        global start_time

        current_time = datetime.datetime.utcnow()
        delta = current_time - start_time

        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)

        embed.add_field(
            name="Uptime",
            value=f"{hours} hours {minutes} minutes {seconds} seconds",
            inline=False,
        )
        embed.set_footer(
            text="Information requested by: {}".format(ctx.author.name),
            icon_url=ctx.author.avatar.url,
        )
        embed.set_thumbnail(
            url="https://uploads.poxipage.com/7q5iw7dwl5jc3zdjaergjhpat27tws8bkr9fgy45_938843265627717703-webp"
        )

        await message.edit(embed=embed)

    except Exception as e:
        print(e, file=sys.stdout)


# @bot.hybrid_command(name="help", description="View the various commands of this server")
# async def help(ctx):
#     user = bot.get_user(1168874960081649684)
#     profilePicture = user.avatar.url

#     embed = discord.Embed(
#         title="SecretSanctuary Bot Commands",
#         url=APP_URI,
#         description="Here is the list of the available commands:",
#         color=discord.Color.og_blurple(),
#     )

#     embed.set_thumbnail(url=profilePicture)
#     for i in commands_.keys():
#         embed.add_field(name=i, value=commands_[i], inline=False)

#     embed.set_footer(
#         text="Information requested by: {}".format(ctx.author.name),
#         icon_url=ctx.author.avatar.url,
#     )

#     await ctx.send(embed=embed)


if __name__ == "__main__":
    # run_server()
    keep_alive()
    bot.run(token=TOKEN)
