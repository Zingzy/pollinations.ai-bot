import random
import aiohttp
import io
from utils.logger import logger
from urllib.parse import quote
import json
from PIL import Image
from exceptions import PromptTooLongError, DimensionTooSmallError, APIError
from config import config

__all__: list[str] = ("generate_image", "validate_prompt", "validate_dimensions")


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
    prompt: str = None,
    width: int = config.image_generation.defaults.width,
    height: int = config.image_generation.defaults.height,
    model: str = config.MODELS[0],
    safe: bool = config.image_generation.defaults.safe,
    cached: bool = config.image_generation.defaults.cached,
    nologo: bool = config.image_generation.defaults.nologo,
    enhance: bool = config.image_generation.defaults.enhance,
    private: bool = config.image_generation.defaults.private,
    **kwargs,
):
    logger.info(
        f"Generating image with prompt: {prompt}, width: {width}, height: {height}, safe: {safe}, cached: {cached}, nologo: {nologo}, enhance: {enhance}, model: {model}"
    )

    seed = str(random.randint(0, 1000000000))

    url: str = f"{config.api.image_gen_endpoint}/{prompt}"
    url += "" if cached else f"?seed={seed}"
    url += f"&width={width}"
    url += f"&height={height}"
    url += f"&model={model}" if model else ""
    url += f"&safe={safe}" if safe else ""
    url += f"&nologo={nologo}" if nologo else ""
    url += f"&enhance={enhance}" if enhance else ""
    url += f"&nofeed={private}" if private else ""
    url += f"&referer={config.image_generation.referer}"

    dic = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "model": model,
        "safe": safe,
        "cached": cached,
        "nologo": nologo,
        "enhance": enhance,
        "url": quote(url, safe=":/&=?"),
    }

    dic["seed"] = None if cached else seed

    headers = {
        "Authorization": f"Bearer {config.api.api_key}",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, allow_redirects=True, headers=headers
            ) as response:
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
                    raise APIError(
                        response.status, "Received empty response from server"
                    )

                user_comment = _extract_user_comment(image_data)

                image_file = io.BytesIO(image_data)
                image_file.seek(0)

                try:
                    dic["nsfw"] = user_comment["has_nsfw_concept"]
                    if (
                        enhance
                        or len(prompt)
                        < config.image_generation.validation.max_enhanced_prompt_length
                    ):
                        enhance_prompt = user_comment["prompt"]
                        if enhance_prompt == prompt:
                            dic["enhanced_prompt"] = None
                        else:
                            enhance_prompt = enhance_prompt[
                                : enhance_prompt.rfind("\n")
                            ].strip()
                            dic["enhanced_prompt"] = enhance_prompt
                except Exception:
                    dic["nsfw"] = False

        return (dic, image_file)
    except aiohttp.ClientError as e:
        raise APIError(500, f"Network error occurred: {str(e)}")


def _extract_user_comment(image_bytes):
    image = Image.open(io.BytesIO(image_bytes))

    try:
        exif = image.info["exif"].decode("latin-1", errors="ignore")
        user_comment = json.loads(exif[exif.find("{") : exif.rfind("}") + 1])
    except Exception:
        logger.exception("Error extracting user comment from image EXIF data")
        return "No user comment found."

    return user_comment if user_comment else "No user comment found."
