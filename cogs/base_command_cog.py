import traceback
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import config
from utils.embed_utils import generate_error_message, SafeEmbed
from utils.error_handler import send_error_embed
from utils.logger import discord_logger
from exceptions import (
    PromptTooLongError,
    DimensionTooSmallError,
    APIError,
    NoImagesGeneratedError,
)


class BaseCommandCog(commands.Cog, ABC):
    """
    Base cog class for image generation commands.
    Provides common functionality like error handling, logging, and validation.
    """

    def __init__(self, bot: commands.Bot, command_name: str) -> None:
        self.bot = bot
        self.command_name = command_name
        self.command_config = config.commands.get(command_name, None)

        if not self.command_config:
            raise ValueError(f"Command configuration not found for '{command_name}'")

    async def cog_load(self) -> None:
        """Called when the cog is loaded. Override in subclasses to add specific setup."""
        await self.bot.wait_until_ready()
        discord_logger.log_bot_event(
            action="cog_load",
            status="success",
            details={"cog": self.__class__.__name__},
        )

    @abstractmethod
    def get_view_class(self):
        """Return the view class that should be used for this command. Must be implemented by subclasses."""
        pass

    def create_cooldown_error_config(self) -> list[str]:
        """Create cooldown configuration for error messages."""
        return [
            f"- {self.command_config.cooldown.rate} time every {self.command_config.cooldown.seconds} seconds",
        ]

    async def handle_cooldown_error(
        self, interaction: discord.Interaction, error: app_commands.CommandOnCooldown
    ) -> None:
        """Handle cooldown errors in a standardized way."""
        discord_logger.log_error(
            error_type="cooldown",
            error_message=str(error),
            context={
                "command": self.command_name,
                "user_id": interaction.user.id,
                "retry_after": error.retry_after,
            },
        )

        embed: SafeEmbed = await generate_error_message(
            interaction,
            error,
            cooldown_configuration=self.create_cooldown_error_config(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def handle_validation_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        error_title: str,
        delete_after_minutes: float = 0.5,
    ) -> None:
        """Handle validation errors in a standardized way."""
        discord_logger.log_error(
            error_type="validation_error",
            error_message=str(error),
            context={"command": self.command_name, "error_type": type(error).__name__},
        )

        await send_error_embed(
            interaction,
            error_title,
            f"```\n{str(error)}\n```",
            delete_after_minutes=delete_after_minutes,
        )

    async def handle_api_error(
        self,
        interaction: discord.Interaction,
        error: APIError,
        delete_after_minutes: float = 2,
    ) -> None:
        """Handle API errors in a standardized way."""
        discord_logger.log_error(
            error_type="api_error",
            error_message=str(error),
            context={"command": self.command_name},
        )

        await send_error_embed(
            interaction,
            "Couldn't Generate the Requested Image 😔",
            f"```\n{str(error)}\n```",
            delete_after_minutes=delete_after_minutes,
        )

    async def handle_unexpected_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        delete_after_minutes: float = 2,
    ) -> None:
        """Handle unexpected errors in a standardized way."""
        error_context = {"command": self.command_name, "user_id": interaction.user.id}
        if context:
            error_context.update(context)

        discord_logger.log_error(
            error_type="unexpected_error",
            error_message=str(error),
            traceback=traceback.format_exception_only(type(error), error),
            context=error_context,
        )

        await send_error_embed(
            interaction,
            "An unexpected error occurred",
            f"```\n{str(error)}\n```",
            delete_after_minutes=delete_after_minutes,
        )

    async def handle_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
        **context,
    ) -> None:
        """
        Centralized error handler for commands.
        This method handles all common error types and can be extended by subclasses.
        """
        if isinstance(error, app_commands.CommandOnCooldown):
            await self.handle_cooldown_error(interaction, error)

        elif isinstance(error, PromptTooLongError):
            await self.handle_validation_error(interaction, error, "Prompt Too Long")

        elif isinstance(error, DimensionTooSmallError):
            await self.handle_validation_error(
                interaction, error, "Dimensions Too Small"
            )

        elif isinstance(error, APIError):
            await self.handle_api_error(interaction, error)

        elif isinstance(error, NoImagesGeneratedError):
            await send_error_embed(
                interaction,
                "Generation Failed",
                f"Failed to generate any images:\n```\n{str(error)}\n```",
                delete_after_minutes=2,
            )

        else:
            await self.handle_unexpected_error(interaction, error, context)

    def log_generation_start(
        self,
        model: str = "unknown",
        dimensions: Dict[str, int] = None,
        cached: bool = False,
        action: str = "generate",
    ) -> None:
        """Log the start of image generation."""
        discord_logger.log_image_generation(
            action=f"{action}_start",
            model=model,
            dimensions=dimensions or {"width": 0, "height": 0},
            generation_time=0,
            status="started",
            cached=cached,
        )

    def log_generation_complete(
        self,
        model: str = "unknown",
        dimensions: Dict[str, int] = None,
        generation_time: float = 0,
        cached: bool = False,
        action: str = "generate",
    ) -> None:
        """Log the completion of image generation."""
        discord_logger.log_image_generation(
            action=f"{action}_complete",
            model=model,
            dimensions=dimensions or {"width": 0, "height": 0},
            generation_time=generation_time,
            status="success",
            cached=cached,
        )

    async def send_response(
        self,
        interaction: discord.Interaction,
        embed: SafeEmbed,
        file: Optional[discord.File] = None,
        view: Optional[discord.ui.View] = None,
        ephemeral: bool = False,
    ) -> None:
        """Send a standardized response."""
        if ephemeral:
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            view = view or self.get_view_class()()
            await interaction.followup.send(embed=embed, view=view, file=file)


async def setup_base_cog(bot: commands.Bot, cog_class: type, command_name: str) -> None:
    """Helper function to setup cogs that inherit from BaseCommandCog."""
    await bot.add_cog(cog_class(bot))
    discord_logger.log_bot_event(
        action="cog_setup", status="success", details={"cog": cog_class.__name__}
    )
