import aiohttp
import io
import asyncio
from typing import Tuple, Dict, Any
from utils.logger import logger
from utils.image_request_builder import ImageRequestBuilder
from exceptions import APIError, DimensionTooSmallError, PromptTooLongError
from config import config
from PIL import Image
import json


def validate_prompt(prompt) -> None:
    if len(prompt) > config.image_generation.validation.max_prompt_length:
        raise PromptTooLongError(config.ui.error_messages["prompt_too_long"])


def validate_dimensions(width, height) -> None:
    if (
        width < config.image_generation.validation.min_width
        or height < config.image_generation.validation.min_height
    ):
        raise DimensionTooSmallError(config.ui.error_messages["dimension_too_small"])


async def generate_image(
    prompt: str,
    width: int = None,
    height: int = None,
    model: str = None,
    safe: bool = None,
    cached: bool = None,
    nologo: bool = None,
    enhance: bool = None,
    private: bool = None,
    negative: str = None,
    **kwargs,
) -> Tuple[Dict[str, Any], io.BytesIO]:
    """
    Generate an image using the new ImageRequestBuilder.

    Args:
        prompt: The text prompt for image generation
        width: Image width (optional, uses default from config)
        height: Image height (optional, uses default from config)
        model: AI model to use (optional, uses default from config)
        safe: Enable safety filter (optional, uses default from config)
        cached: Use cached results (optional, uses default from config)
        nologo: Remove logo (optional, uses default from config)
        enhance: Enhance prompt (optional, uses default from config)
        private: Private generation (optional, uses default from config)
        negative: Negative prompt (optional)
        **kwargs: Additional parameters

    Returns:
        Tuple of (request_data_dict, image_file_bytes)
    """

    # Build the request using the new builder
    builder = ImageRequestBuilder.for_standard_generation(prompt)

    # Apply optional parameters
    if width is not None:
        builder.with_dimensions(
            width, height or config.image_generation.defaults.height
        )
    elif height is not None:
        builder.with_dimensions(config.image_generation.defaults.width, height)

    if model is not None:
        builder.with_model(model)
    if safe is not None:
        builder.with_safety(safe)
    if cached is not None:
        builder.with_caching(cached)
    if nologo is not None:
        builder.with_logo(nologo)
    if enhance is not None:
        builder.with_enhancement(enhance)
    if private is not None:
        builder.with_privacy(private)
    if negative is not None:
        builder.with_negative_prompt(negative)

    # Build the request
    request_data = builder.build_request_data()
    url = request_data["url"]

    logger.info(f"Generating image with builder: {request_data}")

    headers = {
        "Authorization": f"Bearer {config.api.api_key}",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, allow_redirects=True, headers=headers
            ) as response:
                # Handle HTTP errors
                if response.status >= 500:
                    raise APIError(
                        f"Server error occurred while generating image with status code: {response.status}\nPlease try again later"
                    )
                elif response.status == 429:
                    raise APIError(config.ui.error_messages["rate_limit"])
                elif response.status == 404:
                    raise APIError(config.ui.error_messages["resource_not_found"])
                elif response.status != 200:
                    raise APIError(
                        f"API request failed with status code: {response.status}",
                    )

                image_data = await response.read()

                if not image_data:
                    raise APIError("Received empty response from server")

                # Process image metadata asynchronously
                user_comment = await _extract_user_comment_async(image_data)

                image_file = io.BytesIO(image_data)
                image_file.seek(0)

                # Update request data with metadata
                try:
                    request_data["nsfw"] = user_comment["has_nsfw_concept"]
                    if (
                        enhance
                        or len(prompt)
                        < config.image_generation.validation.max_enhanced_prompt_length
                    ):
                        enhance_prompt = user_comment["prompt"]
                        if enhance_prompt != prompt:
                            enhance_prompt = enhance_prompt[
                                : enhance_prompt.rfind("\n")
                            ].strip()
                            request_data["enhanced_prompt"] = enhance_prompt
                        else:
                            request_data["enhanced_prompt"] = None
                except Exception:
                    request_data["nsfw"] = False

        return (request_data, image_file)

    except aiohttp.ClientError as e:
        raise APIError(f"Network error occurred: {str(e)}")


async def generate_cross_pollinate(
    prompt: str, image_url: str, nologo: bool = None
) -> Tuple[Dict[str, Any], io.BytesIO]:
    """
    Generate a cross-pollinated/edited image using the new ImageRequestBuilder.

    Args:
        prompt: The edit prompt
        image_url: URL of the source image
        nologo: Remove logo (optional, uses default from config)

    Returns:
        Tuple of (request_data_dict, image_file_bytes)
    """

    # Build the request using the cross-pollination builder
    builder = ImageRequestBuilder.for_cross_pollination(prompt, image_url)

    if nologo is not None:
        builder.with_logo(nologo)

    # Build the request
    request_data = builder.build_request_data()
    url = request_data["url"]

    logger.info(f"Cross-pollinating image with builder: {request_data}")

    headers = {
        "Authorization": f"Bearer {config.api.api_key}",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, allow_redirects=True, headers=headers
            ) as response:
                # Handle HTTP errors
                if response.status >= 500:
                    raise APIError(
                        f"Server error occurred while editing image with status code: {response.status}\nPlease try again later"
                    )
                elif response.status == 429:
                    raise APIError(config.ui.error_messages["rate_limit"])
                elif response.status == 404:
                    raise APIError(config.ui.error_messages["resource_not_found"])
                elif response.status != 200:
                    raise APIError(
                        f"API request failed with status code: {response.status}",
                    )

                image_data = await response.read()

                if not image_data:
                    raise APIError("Received empty response from server")

                image_file = io.BytesIO(image_data)
                image_file.seek(0)

                # Set basic metadata for cross-pollination
                request_data["nsfw"] = False  # Default for editing

        return (request_data, image_file)

    except aiohttp.ClientError as e:
        raise APIError(f"Network error occurred: {str(e)}")


async def generate_random_image(
    width: int = None,
    height: int = None,
    model: str = None,
    negative: str = None,
    nologo: bool = None,
    private: bool = None,
    **kwargs,
) -> Tuple[Dict[str, Any], io.BytesIO]:
    """
    Generate a random image using the new ImageRequestBuilder.

    Args:
        width: Image width (optional, uses default from config)
        height: Image height (optional, uses default from config)
        model: AI model to use (optional, uses default from config)
        negative: Negative prompt (optional)
        nologo: Remove logo (optional, uses default from config)
        private: Private generation (optional, uses default from config)
        **kwargs: Additional parameters

    Returns:
        Tuple of (request_data_dict, image_file_bytes)
    """

    # Build the request using the random generation builder
    builder = ImageRequestBuilder.for_random_generation()

    # Apply optional parameters
    if width is not None:
        builder.with_dimensions(
            width, height or config.image_generation.defaults.height
        )
    elif height is not None:
        builder.with_dimensions(config.image_generation.defaults.width, height)

    if model is not None:
        builder.with_model(model)
    if negative is not None:
        builder.with_negative_prompt(negative)
    if nologo is not None:
        builder.with_logo(nologo)
    if private is not None:
        builder.with_privacy(private)

    # Build the request
    request_data = builder.build_request_data()
    url = request_data["url"]

    logger.info(f"Generating random image with builder: {request_data}")

    headers = {
        "Authorization": f"Bearer {config.api.api_key}",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, allow_redirects=True, headers=headers
            ) as response:
                # Handle HTTP errors
                if response.status >= 500:
                    raise APIError(
                        f"Server error occurred while generating random image with status code: {response.status}\nPlease try again later"
                    )
                elif response.status == 429:
                    raise APIError(config.ui.error_messages["rate_limit"])
                elif response.status == 404:
                    raise APIError(config.ui.error_messages["resource_not_found"])
                elif response.status != 200:
                    raise APIError(
                        f"API request failed with status code: {response.status}",
                    )

                image_data = await response.read()

                if not image_data:
                    raise APIError("Received empty response from server")

                # Process image metadata asynchronously
                user_comment = await _extract_user_comment_async(image_data)

                image_file = io.BytesIO(image_data)
                image_file.seek(0)

                # Update request data with metadata
                try:
                    request_data["nsfw"] = user_comment["has_nsfw_concept"]
                    # For random images, always use the enhanced prompt
                    enhance_prompt = user_comment["prompt"]
                    if enhance_prompt:
                        enhance_prompt = enhance_prompt[
                            : enhance_prompt.rfind("\n")
                        ].strip()
                        request_data["enhanced_prompt"] = enhance_prompt
                except Exception:
                    request_data["nsfw"] = False

        return (request_data, image_file)

    except aiohttp.ClientError as e:
        raise APIError(f"Network error occurred: {str(e)}")


async def _extract_user_comment_async(image_bytes):
    """Extract user comment from image EXIF data asynchronously"""
    loop = asyncio.get_event_loop()

    def _extract_sync():
        try:
            image = Image.open(io.BytesIO(image_bytes))
            exif = image.info["exif"].decode("latin-1", errors="ignore")
            user_comment = json.loads(exif[exif.find("{") : exif.rfind("}") + 1])
            return (
                user_comment
                if user_comment
                else {"has_nsfw_concept": False, "prompt": ""}
            )
        except Exception:
            logger.exception("Error extracting user comment from image EXIF data")
            return {"has_nsfw_concept": False, "prompt": ""}

    # Run the CPU-intensive PIL operation in a thread pool
    return await loop.run_in_executor(None, _extract_sync)

