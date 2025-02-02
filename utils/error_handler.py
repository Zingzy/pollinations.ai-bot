from discord import Embed, Interaction
from config import config


async def send_error_embed(
    interaction: Interaction, title: str, description: str = None
) -> None:
    if not description:
        description = config.ui.error_messages["unknown"]

    embed = Embed(
        title=title, description=description, color=int(config.ui.colors.error, 16)
    )

    if not interaction.response.is_done():
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.followup.send(embed=embed, ephemeral=True)
