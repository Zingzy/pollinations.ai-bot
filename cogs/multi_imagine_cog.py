import datetime
import discord
from discord import app_commands, ui
from discord.ext import commands

from utils import *
from constants import *

class Multi_imagine(commands.Cog):
    def __init(self, bot):
        self.bot = bot

    @app_commands.command(name="multi-imagine", description="Imagine multiple prompts")
    @app_commands.checks.cooldown(1, 30)
    @app_commands.describe(prompt="Imagine a prompt", height="Height of the image", width="Width of the image", negative="The things not to include in the image", cached="Removes the image seed", nologo="Remove the logo", enhance="Disables Prompt enhancing if set to False", private="Only you can see the generated Image if set to True")
    async def multiimagine_command(self, interaction, prompt:str, width:int = 1000, height:int = 1000, negative:str|None = None, cached:bool = False, nologo:bool = False, enhance:bool = True, private:bool = False):

        await interaction.response.send_message(embed=discord.Embed(title="Generating Image", description="Please wait while we generate your image", color=discord.Color.blurple()), ephemeral=True)

        models = ['Deliberate', 'Playground', 'Pixart', 'Dreamshaper', 'Turbo', 'Formulaxl', 'Dpo']

        if len(prompt) > 1500:
            await interaction.channel.send(embed=discord.Embed(title="Error", description="Prompt must be less than 1500 characters", color=discord.Color.red()))
            return

        if width < 16 or height < 16:
            await interaction.channel.send(embed=discord.Embed(title="Error", description="Width and Height must be greater than 16", color=discord.Color.red()))
            return

        images = []
        description = ""
        counter = 1

        for i in models:
            try:
                time = datetime.datetime.now()
                dic, image = await generate_image(prompt, width, height, i, negative, cached, nologo, enhance)
                time_taken = datetime.datetime.now() - time
                await interaction.followup.send(f"Generated `{i} model` Image in `{round(time_taken.total_seconds(), 2)}` seconds ✅", ephemeral=True)
                description += f"Image {counter} model :  `{i}`\n"
                counter += 1
                images.append(image)
            except Exception as e:
                print(e)
                await interaction.followup.send(embed=discord.Embed(title=f"Error generating image of `{i}` model", description=f"{e}", color=discord.Color.red()), ephemeral=True)

        files = []

        is_nsfw = False
        for i in prompt.split(" "):
            if i.lower() in NSFW_WORDS:
                is_nsfw = True

        for idx, img in enumerate(images):
            file_name = f"{prompt}_{idx}.png" if not is_nsfw else f"SPOILER_{prompt}_{idx}.png"
            files.append(discord.File(img, file_name))

        if not len(files) == 0:
            if private:
                response = await interaction.followup.send(f'## {prompt} - {interaction.user.mention}\n{description}', files=files, ephemeral= True)
            else:
                response = await interaction.channel.send(f'## {prompt} - {interaction.user.mention}\n{description}', files=files)
        else:
            await interaction.followup.send(embed=discord.Embed(title="Error", description="No images were generated", color=discord.Color.red()), ephemeral=True)
            return

    @multiimagine_command.error
    async def multiimagine_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.CommandOnCooldown):
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
                description=f"You have to wait until **{end_time_ts}** ({time_left}) before using the </multi-imagine:1187375074722975837> again.",
                color=discord.Color.red(),
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Multi_imagine(bot))
    print("Multi-Imagine cog loaded")