import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ["TOKEN"]
MONGODB_URI = os.environ["MONGODB_URI"]
APP_URI = os.environ["APP_URI"]
MODELS = [
    "swizz8",
    "dreamshaper",
    "deliberate",
    "juggernaut",
]

with open("nsfw.txt", "r") as r:
    nsfw = r.read().split("\n")
    NSFW_WORDS = [i.strip() for i in nsfw if i.strip() != ""]
