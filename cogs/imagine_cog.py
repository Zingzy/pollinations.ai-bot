import datetime
import random
import discord
from discord import app_commands, ui
from discord.ext import commands
from discord.ui import Button
import json

from utils import *
from constants import *


class Imagine(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        await self.bot.wait_until_ready()
        self.bot.add_view(self.ImagineButtonView())

    class ImagineButtonView(discord.ui.View):
        def __init__(self, link: str = None):
            super().__init__(timeout=None)
            self.link = link

            if link is not None:
                self.add_item(discord.ui.Button(label="Link", url=self.link))

        @discord.ui.button(style=discord.ButtonStyle.secondary, custom_id="regenerate-button", emoji="<:redo:1187101382101180456>")
        async def regenerate(self, interaction: discord.Interaction, button: discord.ui.Button):
            message_id = interaction.message.id
            await interaction.response.send_message(embed=discord.Embed(title="Regenerating Your Image", description="Please wait while we generate your image", color=discord.Color.blurple()), ephemeral=True)

            message_data = get_prompt_data(message_id)

            if not message_data:
                await interaction.followup.send(embed=discord.Embed(title="Error", description="Message not found", color=discord.Color.red()), ephemeral=True)
                return

            prompt = message_data["prompt"]
            width = message_data["width"]
            height = message_data["height"]
            model = message_data["model"]
            negative = message_data["negative"]
            cached = message_data["cached"]
            nologo = message_data["nologo"]
            enhance = message_data["enhance"]

            try:
                dic, image = await generate_image(prompt, width, height, model, negative, cached, nologo, enhance)
            except Exception as e:
                print(e)
                await interaction.followup.send(embed=discord.Embed(title="Error", description=f"Error generating image : {e}", color=discord.Color.red()), ephemeral=True)
                return

            image_file = discord.File(image, filename="image.png")

            response = await interaction.channel.send(f"## {prompt} - {interaction.user.mention}", file=image_file, view=self)

            dic["_id"] = response.id
            dic["channel_id"] = interaction.channel.id
            dic["user_id"] = interaction.user.id
            dic["guild_id"] = interaction.guild.id
            dic["author"] = interaction.user.id
            dic["bookmarks"] = []
            dic["likes"] = []

            save_prompt_data(message_id, dic)

        @discord.ui.button(label="0", style=discord.ButtonStyle.secondary, custom_id="like-button", emoji="<:like:1187101385230143580>")
        async def like(self, interaction: discord.Interaction, button: discord.ui.Button):
            try:
                id = interaction.message.id
                message_data = get_prompt_data(id)
                likes = message_data["likes"]

                if interaction.user.id in likes:
                    likes.remove(interaction.user.id)
                    update_prompt_data(id, {"likes": likes})
                    button.label = f"{len(likes)}"
                    await interaction.response.edit_message(view=self)
                    return
                else:
                    likes.append(interaction.user.id)
                    update_prompt_data(id, {"likes": likes})
                    button.label = f"{len(likes)}"
                    await interaction.response.edit_message(view=self)
                    return
            except Exception as e:
                print(e)
                interaction.response.send_message(embed=discord.Embed(title="Error Liking the Image", description=f"{e}", color=discord.Color.red()), ephemeral=True)

        @discord.ui.button(label = "0", style=discord.ButtonStyle.secondary, custom_id="bookmark-button", emoji="<:save:1187101389822902344>")
        async def bookmark(self, interaction: discord.Interaction, button: discord.ui.Button):
            try:
                id = interaction.message.id
                message_data = get_prompt_data(id)
                bookmarks = message_data["bookmarks"]

                if interaction.user.id in bookmarks:
                    await interaction.response.send_message(embed=discord.Embed(title="Error", description="You have already bookmarked this image", color=discord.Color.red()), ephemeral=True)
                else:
                    bookmarks.append(interaction.user.id)
                    update_prompt_data(id, {"bookmarks": bookmarks})
                    button.label = f"{len(bookmarks)}"
                    await interaction.response.edit_message(view=self)

                    embed = discord.Embed(title=f"Prompt : {message_data['prompt']}", description=f"url : {message_data['bookmark_url']}", color=discord.Color.og_blurple())
                    embed.set_image(url=message_data["bookmark_url"])

                    await interaction.user.send(embed=embed)
                    return

            except Exception as e:
                print(e)
                await interaction.response.send_message(embed=discord.Embed(title="Error Bookmarking the Image", description=f"{e}", color=discord.Color.red()), ephemeral=True)

        @discord.ui.button(style=discord.ButtonStyle.red, custom_id="delete-button", emoji="<:delete:1187102382312652800>")
        async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
            try:
                data = get_prompt_data(interaction.message.id)
                author_id = data["author"]
                try:
                    int(author_id)
                except:
                    pass

                if interaction.user.id != author_id:
                    await interaction.response.send_message(embed=discord.Embed(title="Error", description="You can only delete your own images", color=discord.Color.red()), ephemeral=True)
                    return

                delete_prompt_data(interaction.message.id)
                await interaction.message.delete()

            except Exception as e:
                print(e)
                await interaction.response.send_message(embed=discord.Embed(title="Error Deleting the Image", description=f"{e}", color=discord.Color.red()), ephemeral=True)


    async def model_autocomplete(self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        models = ['Deliberate', 'Playground', 'Pixart', 'Dreamshaper', 'Turbo', 'Formulaxl', "Dpo"]
        return [
            app_commands.Choice(name=choice, value=choice)
            for choice in models if current.lower() in choice.lower()
        ]


    @app_commands.command(name="imagine", description="Imagine a prompt")
    @app_commands.autocomplete(model=model_autocomplete)
    @app_commands.describe(prompt="Imagine a prompt", height="Height of the image", width="Width of the image", negative="The things not to include in the image", cached="Removes the image seed", nologo="Remove the logo", enhance="Disables Prompt enhancing if set to False", private="Only you can see the generated Image if set to True")
    async def imagine_command(self, interaction, prompt:str, model: str = "Dreamshaper", width:int = 1000, height:int = 1000, negative:str|None = None, cached:bool = False, nologo:bool = False, enhance:bool = True, private:bool = False):
        await interaction.response.send_message(embed=discord.Embed(title="Generating Image", description="Please wait while we generate your image", color=discord.Color.blurple()), ephemeral=True)

        if len(prompt) > 1500:
            await interaction.channel.send(embed=discord.Embed(title="Error", description="Prompt must be less than 1500 characters", color=discord.Color.red()))
            return

        if width < 16 or height < 16:
            await interaction.channel.send(embed=discord.Embed(title="Error", description="Width and Height must be greater than 16", color=discord.Color.red()))
            return

        try:
            dic, image = await generate_image(prompt, width, height, model, negative, cached, nologo, enhance)
        except Exception as e:
            print(e)
            await interaction.channel.send(embed=discord.Embed(title="Error", description=f"Error generating image : {e}", color=discord.Color.red()))
            return

        image_file = discord.File(image, filename="image.png")

        view = self.ImagineButtonView(link=dic["bookmark_url"])

        if private:
            response = await interaction.followup.send(f"## {prompt} - {interaction.user.mention}", file=image_file, ephemeral=True, view=view)
        else:
            response = await interaction.channel.send(f"## {prompt} - {interaction.user.mention}", file=image_file, view=view)

        message_id = response.id
        dic["_id"] = message_id
        dic["channel_id"] = interaction.channel.id
        dic["user_id"] = interaction.user.id
        dic["guild_id"] = interaction.guild.id
        dic["bookmarks"] = []
        dic["author"] = interaction.user.id
        dic["likes"] = []

        save_prompt_data(message_id, dic)

        return

    @app_commands.command(name="multi-imagine", description="Imagine multiple prompts")
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
                await interaction.followup.send(f"Generated {i} model Image\nTime taken : `{time_taken.total_seconds()}`", ephemeral=True)
                description += f"Image {counter} model :  `{i}`\n"
                counter += 1
                images.append(image)
            except Exception as e:
                print(e)
                await interaction.followup.send(embed=discord.Embed(title=f"Error generating image of `{i}` model", description=f"{e}", color=discord.Color.red()), ephemeral=True)

        files = []

        for idx, img in enumerate(images):
            file_name = f"{prompt}_{idx}.png"
            files.append(discord.File(img, file_name))

        response = await interaction.followup.send(f'## `{prompt}` - {interaction.user.mention}\n{description}', files=files, ephemeral= False) if private else await interaction.channel.send(f'## `{prompt}` - {interaction.user.mention}\n{description}', files=files)

        # id = response.id
        # dic["message_id"] = id
        # dic["type"] = "multi"
        # dic["channel_id"] = interaction.channel.id
        # dic["user_id"] = interaction.user.id
        # dic["guild_id"] = interaction.guild.id

        return

async def setup(bot):
    await bot.add_cog(Imagine(bot))
    print("Imagine cog loaded")