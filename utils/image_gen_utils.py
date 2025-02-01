import random
from constants import MODELS
import aiohttp
import io
from urllib.parse import quote
import sys
import json
from PIL import Image
from exceptions import PromptTooLongError, DimensionTooSmallError, APIError

__all__: list[str] = ("generate_image", "validate_prompt", "validate_dimensions")


def validate_prompt(prompt) -> None:
    if len(prompt) > 2000:
        raise PromptTooLongError("Prompt must be less than 2000 characters")


def validate_dimensions(width, height) -> None:
    if width < 16 or height < 16:
        raise DimensionTooSmallError("Width and Height must be greater than 16")


async def generate_image(
    prompt: str = None,
    width: int = 800,
    height: int = 800,
    model: str = f"{MODELS[0]}",
    safe: bool = False,
    cached: bool = False,
    nologo: bool = False,
    enhance: bool = False,
    private: bool = False,
    **kwargs,
):
    print(
        f"Generating image with prompt: {prompt}, width: {width}, height: {height}, safe: {safe}, cached: {cached}, nologo: {nologo}, enhance: {enhance}, model: {model}",
        file=sys.stderr,
    )

    seed = str(random.randint(0, 1000000000))

    url: str = f"https://image.pollinations.ai/prompt/{prompt}"
    url += f"?seed={seed}" if not cached else ""
    url += f"&width={width}"
    url += f"&height={height}"
    url += f"&model={model}"
    url += f"&safe={safe}" if safe else ""
    url += f"&nologo={nologo}" if nologo else ""
    url += f"&enhance={enhance}" if enhance else ""
    url += f"&nofeed={private}" if private else ""
    url += "&referer=discordbot"

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

    dic["seed"] = seed if not cached else None

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, allow_redirects=True) as response:
                if response.status >= 500:
                    raise APIError(
                        f"Server error occurred while generating image with status code: {response.status}\nPlease try again later"
                    )
                elif response.status == 429:
                    raise APIError("Rate limit exceeded. Please try again later")
                elif response.status == 404:
                    raise APIError("The requested resource was not found")
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
                    if enhance or len(prompt) < 80:
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
        return "No user comment found."

    if user_comment:
        return user_comment
    else:
        return "No user comment found."
