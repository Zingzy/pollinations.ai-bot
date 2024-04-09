import os
from dotenv import load_dotenv

load_dotenv(override=True)

TOKEN = os.environ["TOKEN"]
MONGODB_URI = os.environ["MONGODB_URI"]
MODELS = [
    "dreamshaper",
    "swizz8",
    "deliberate",
    "juggernaut",
]

with open("nsfw.txt", "r") as r:
    nsfw = r.read().split("\n")
    NSFW_WORDS = [i.strip() for i in nsfw if i.strip() != ""]
