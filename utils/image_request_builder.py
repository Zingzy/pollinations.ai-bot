import random
from typing import Optional, Dict, Any
from urllib.parse import quote
from dataclasses import dataclass, asdict
from config import config


@dataclass
class ImageRequest:
    """Data class representing an image generation request."""

    prompt: Optional[str] = None
    width: int = config.image_generation.defaults.width
    height: int = config.image_generation.defaults.height
    model: Optional[str] = None
    safe: bool = config.image_generation.defaults.safe
    cached: bool = config.image_generation.defaults.cached
    nologo: bool = config.image_generation.defaults.nologo
    enhance: bool = config.image_generation.defaults.enhance
    private: bool = config.image_generation.defaults.private
    negative: Optional[str] = None
    seed: Optional[str] = None
    image_url: Optional[str] = None  # For cross-pollination/editing

    def __post_init__(self):
        """Post-initialization to set defaults and generate seed if needed."""
        if self.model is None:
            self.model = (
                config.MODELS[0]
                if config.MODELS
                else config.image_generation.fallback_model
            )

        if not self.cached and self.seed is None:
            self.seed = str(random.randint(0, 1000000000))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        data = asdict(self)
        return {k: v for k, v in data.items() if v is not None}


class ImageRequestBuilder:
    """Builder class for constructing image generation API requests."""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or config.api.image_gen_endpoint
        self.request = ImageRequest()

    def with_prompt(self, prompt: str) -> "ImageRequestBuilder":
        """Set the prompt for image generation."""
        self.request.prompt = prompt
        return self

    def with_dimensions(self, width: int, height: int) -> "ImageRequestBuilder":
        """Set the image dimensions."""
        self.request.width = width
        self.request.height = height
        return self

    def with_model(self, model: str) -> "ImageRequestBuilder":
        """Set the AI model to use."""
        self.request.model = model
        return self

    def with_safety(self, safe: bool) -> "ImageRequestBuilder":
        """Set safety filter."""
        self.request.safe = safe
        return self

    def with_caching(self, cached: bool) -> "ImageRequestBuilder":
        """Set whether to use cached results."""
        self.request.cached = cached
        return self

    def with_logo(self, nologo: bool) -> "ImageRequestBuilder":
        """Set whether to remove logo."""
        self.request.nologo = nologo
        return self

    def with_enhancement(self, enhance: bool) -> "ImageRequestBuilder":
        """Set whether to enhance the prompt."""
        self.request.enhance = enhance
        return self

    def with_privacy(self, private: bool) -> "ImageRequestBuilder":
        """Set whether the result should be private."""
        self.request.private = private
        return self

    def with_negative_prompt(self, negative: str) -> "ImageRequestBuilder":
        """Set negative prompt (things to avoid)."""
        self.request.negative = negative
        return self

    def with_seed(self, seed: str) -> "ImageRequestBuilder":
        """Set specific seed for reproducible results."""
        self.request.seed = seed
        return self

    def with_source_image(self, image_url: str) -> "ImageRequestBuilder":
        """Set source image for cross-pollination/editing."""
        self.request.image_url = image_url
        return self

    def build_url(self) -> str:
        """Build the complete API URL."""
        if not self.request.prompt:
            raise ValueError("Prompt is required for image generation")

        # Start with base URL and prompt
        url = f"{self.base_url}/{self.request.prompt}"

        # Build query parameters
        params = []

        # Add seed if not cached
        if not self.request.cached and self.request.seed:
            params.append(f"seed={self.request.seed}")

        # Add dimensions
        params.append(f"width={self.request.width}")
        params.append(f"height={self.request.height}")

        # Add model if specified
        if self.request.model:
            params.append(f"model={self.request.model}")

        # Add safety filter
        if self.request.safe:
            params.append(f"safe={self.request.safe}")

        # Add logo setting
        if self.request.nologo:
            params.append(f"nologo={self.request.nologo}")

        # Add enhancement setting
        if self.request.enhance:
            params.append(f"enhance={self.request.enhance}")

        # Add privacy setting
        if self.request.private:
            params.append(f"nofeed={self.request.private}")

        # Add negative prompt
        if self.request.negative:
            params.append(f"negative={quote(self.request.negative)}")

        # Add source image for cross-pollination
        if self.request.image_url:
            params.append(f"image={quote(self.request.image_url, safe='')}")

        # Add referer
        params.append(f"referer={config.image_generation.referer}")

        # Combine URL with parameters
        if params:
            url += "?" + "&".join(params)

        return quote(url, safe=":/&=?")

    def build_request_data(self) -> Dict[str, Any]:
        """Build request data dictionary for logging and processing."""
        data = self.request.to_dict()
        data["url"] = self.build_url()
        return data

    def reset(self) -> "ImageRequestBuilder":
        """Reset the builder to create a new request."""
        self.request = ImageRequest()
        return self

    @classmethod
    def for_standard_generation(cls, prompt: str, **kwargs) -> "ImageRequestBuilder":
        """Create a builder for standard image generation."""
        builder = cls()
        builder.with_prompt(prompt)

        # Apply any additional parameters
        for key, value in kwargs.items():
            if hasattr(builder, f"with_{key}"):
                getattr(builder, f"with_{key}")(value)

        return builder

    @classmethod
    def for_cross_pollination(
        cls, prompt: str, image_url: str, **kwargs
    ) -> "ImageRequestBuilder":
        """Create a builder for cross-pollination/editing."""
        builder = cls()
        builder.with_prompt(prompt)
        builder.with_source_image(image_url)
        builder.with_model("gptimage")  # Cross-pollination uses gptimage model

        # Apply any additional parameters
        for key, value in kwargs.items():
            if hasattr(builder, f"with_{key}"):
                getattr(builder, f"with_{key}")(value)

        return builder

    @classmethod
    def for_random_generation(cls, **kwargs) -> "ImageRequestBuilder":
        """Create a builder for random image generation."""
        builder = cls()
        builder.with_prompt("Random Prompt")
        builder.with_enhancement(True)  # Always enhance random prompts

        # Apply any additional parameters
        for key, value in kwargs.items():
            if hasattr(builder, f"with_{key}"):
                getattr(builder, f"with_{key}")(value)

        return builder


class MultiImageRequestBuilder:
    """Builder for creating multiple image requests across different models."""

    def __init__(self, base_request: ImageRequest = None):
        self.base_request = base_request or ImageRequest()
        self.models = (
            config.MODELS.copy()
            if config.MODELS
            else [config.image_generation.fallback_model]
        )

    def with_base_prompt(self, prompt: str) -> "MultiImageRequestBuilder":
        """Set the base prompt for all models."""
        self.base_request.prompt = prompt
        return self

    def with_base_dimensions(
        self, width: int, height: int
    ) -> "MultiImageRequestBuilder":
        """Set dimensions for all models."""
        self.base_request.width = width
        self.base_request.height = height
        return self

    def with_models(self, models: list) -> "MultiImageRequestBuilder":
        """Set specific models to use."""
        self.models = models
        return self

    def build_requests(self) -> list[ImageRequestBuilder]:
        """Build a list of request builders, one for each model."""
        builders = []

        for model in self.models:
            builder = ImageRequestBuilder()

            # Copy all base request parameters
            builder.request = ImageRequest(**asdict(self.base_request))
            builder.with_model(model)

            builders.append(builder)

        return builders

    def build_urls(self) -> list[str]:
        """Build a list of URLs for all models."""
        return [builder.build_url() for builder in self.build_requests()]
