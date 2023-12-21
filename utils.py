import random
from constants import *
import aiohttp
import io
from urllib.parse import quote
from pymongo import MongoClient
import sys

client = MongoClient(MONGODB_URI)

try:
    client.admin.command("ping")
    print("\n Pinged your deployment. You successfully connected to MongoDB! \n")
except Exception as e:
    print(e)

db = client["pollinations"]
collection = db["prompts"]


def get_prompt_data(message_id: int):
    try:
        return collection.find_one({"_id": message_id})
    except Exception as e:
        print(e)
        return None


def save_prompt_data(message_id: int, data: dict):
    try:
        collection.insert_one(data)
    except Exception as e:
        print(e)


def update_prompt_data(message_id: int, data: dict):
    try:
        collection.update_one({"_id": message_id}, {"$set": data})
    except Exception as e:
        print(e)


def delete_prompt_data(message_id: int):
    try:
        collection.delete_one({"_id": message_id})
    except Exception as e:
        print(e)


async def generate_image(
    prompt: str,
    width: int = 500,
    height: int = 500,
    model: str = "turbo",
    negative: str | None = None,
    cached: bool = False,
    nologo: bool = False,
    enhance: bool = True,
):
    model = model.lower()

    print(
        f"Generating image with prompt: {prompt}, width: {width}, height: {height}, model: {model}, negative: {negative}, cached: {cached}, nologo: {nologo}, enhance: {enhance}", file=sys.stderr
    )

    seed = str(random.randint(0, 1000000000))

    url = f"https://image.pollinations.ai/prompt/{prompt}"
    url += f"?seed={seed}" if not cached else ""
    url += f"&width={width}"
    url += f"&height={height}"
    url += f"&model={model}" if model else ""
    url += f"&negative={negative}" if negative else ""
    url += f"&nologo={nologo}" if nologo else ""
    url += f"&enhance={enhance}" if enhance == False else ""

    dic = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "model": model,
        "negative": negative,
        "cached": cached,
        "nologo": nologo,
        "enhance": enhance,
        "bookmark_url": quote(url, safe=":/&=?"),
    }

    dic["seed"] = seed if not cached else None

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()  # Raise an exception for non-2xx status codes
            image_data = await response.read()
            return (dic, io.BytesIO(image_data))
