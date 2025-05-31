from discord import Interaction
from config import config
from utils.embed_utils import SafeEmbed


async def send_error_embed(
    interaction: Interaction, title: str, description: str = None
) -> None:
    if not description:
        description = config.ui.error_messages["unknown"]

    embed = SafeEmbed(
        title=title, description=description, color=int(config.ui.colors.error, 16)
    )

    if not interaction.response.is_done():
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        # try to delete the previous message
        try:
            await interaction.followup.delete_previous_message()
        except Exception:
            pass
        await interaction.followup.send(embed=embed, ephemeral=True)
