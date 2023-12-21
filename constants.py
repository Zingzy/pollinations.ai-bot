import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ["TOKEN"]
MONGODB_URI = os.environ["MONGODB_URI"]
APP_URI = os.environ["APP_URI"]
