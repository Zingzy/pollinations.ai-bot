from pydantic import BaseModel, model_validator
import tomli
from typing import List, Dict, Optional
from pathlib import Path
import sys


class BotConfig(BaseModel):
    command_prefix: str
    bot_id: str
    avatar_url: str
    commands: Dict[str, str]
    emojis: Dict[str, str]


class APIConfig(BaseModel):
    models_list_endpoint: str
    image_gen_endpoint: str
    models_refresh_interval_minutes: int
    max_timeout_seconds: int


class ImageGenerationDefaults(BaseModel):
    width: int
    height: int
    safe: bool
    cached: bool
    nologo: bool
    enhance: bool
    private: bool


class ImageGenerationValidation(BaseModel):
    min_width: int
    min_height: int
    max_prompt_length: int
    max_enhanced_prompt_length: int = 80


class CommandCooldown(BaseModel):
    rate: int
    seconds: int
    per_minute: Optional[int] = None
    per_day: Optional[int] = None


class CommandConfig(BaseModel):
    cooldown: CommandCooldown
    default_width: int
    default_height: int
    timeout_seconds: Optional[int] = None
    max_prompt_length: Optional[int] = None


class UIColors(BaseModel):
    success: str
    error: str
    warning: str


class UIConfig(BaseModel):
    bot_invite_url: str
    support_server_url: str
    github_repo_url: str
    api_provider_url: str
    bot_creator_avatar: str
    colors: UIColors
    error_messages: Dict[str, str]


class ResourcesConfig(BaseModel):
    waiting_gifs: List[str]


class ImageGenerationConfig(BaseModel):
    referer: str
    fallback_model: str
    defaults: ImageGenerationDefaults
    validation: ImageGenerationValidation


class Config(BaseModel):
    bot: BotConfig
    api: APIConfig
    image_generation: ImageGenerationConfig
    commands: Dict[str, CommandConfig]
    ui: UIConfig
    resources: ResourcesConfig
    MODELS: List[str] = []  # Initialize with empty list as default

    @model_validator(mode="after")
    def validate_structure(self):
        required_commands = {"pollinate", "multi_pollinate", "random"}
        if not all(cmd in self.commands for cmd in required_commands):
            missing = required_commands - self.commands.keys()
            raise ValueError(f"Missing required commands: {missing}")
        return self


def load_config(path: str = "config.toml") -> Config:
    """Load and validate config from TOML file"""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found at {config_path}")

    with open(config_path, "rb") as f:
        config_data = tomli.load(f)

    return Config(**config_data)


def initialize_models(config_instance: Config) -> List[str]:
    """Pre-initialize models list by fetching from the API"""
    import requests

    try:
        response = requests.get(config_instance.api.models_list_endpoint)
        if response.ok:
            return response.json()
    except Exception as e:
        print(f"Error pre-initializing models: {e}", file=sys.stderr)
    return [config_instance.image_generation.fallback_model]


# Load config on import
try:
    config: Config = load_config()
    # Pre-initialize models list
    config.MODELS = initialize_models(config)
except Exception as e:
    raise RuntimeError(f"Failed to load config: {e}") from e
