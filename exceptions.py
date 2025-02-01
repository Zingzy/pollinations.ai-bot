import discord


class PromptTooLongError(discord.app_commands.AppCommandError):
    pass


class DimensionTooSmallError(discord.app_commands.AppCommandError):
    pass


class NoImagesGeneratedError(Exception):
    pass


class ImageGenerationError(Exception):
    def __init__(self, message, model_index: int) -> None:
        super().__init__(message)
        self.model_index: int = model_index


class APIError(Exception):
    pass
