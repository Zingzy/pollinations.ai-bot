import discord


# Create and sends an error embed
async def send_error_embed(
    interaction: discord.Interaction, title: str, description: str
):
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.red(),
    )
    # Try different methods to send the error message
    for send_method in [
        lambda: interaction.response.send_message(embed=embed, ephemeral=True),
        lambda: interaction.edit_original_response(embed=embed),
        lambda: interaction.followup.send(embed=embed, ephemeral=True),
    ]:
        try:
            return await send_method()
        except Exception:
            continue
