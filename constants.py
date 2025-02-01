import os
from dotenv import load_dotenv
import requests
import json

load_dotenv(override=True)

TOKEN: str = os.environ["TOKEN"]
MONGODB_URI: str = os.environ["MONGODB_URI"]

r: requests.Response = requests.get("https://image.pollinations.ai/models")
MODELS: list[str] = json.loads(r.text)

WAITING_GIFS: list[str] = [
    "https://media3.giphy.com/media/l0HlBO7eyXzSZkJri/giphy.gif?cid=ecf05e475p246q1gdcu96b5mkqlqvuapb7xay2hywmki7f5q&ep=v1_gifs_search&rid=giphy.gif&ct=g",
    "https://media2.giphy.com/media/QBd2kLB5qDmysEXre9/giphy.gif?cid=ecf05e47ha6xwa7rq38dcst49nefabwwrods631hvz67ptfg&ep=v1_gifs_search&rid=giphy.gif&ct=g",
    "https://media2.giphy.com/media/ZgqJGwh2tLj5C/giphy.gif?cid=ecf05e47gflyso481izbdcrw7y8okfkgdxgc7zoh34q9rxim&ep=v1_gifs_search&rid=giphy.gif&ct=g",
    "https://media0.giphy.com/media/EWhLjxjiqdZjW/giphy.gif?cid=ecf05e473fifxe2bg4act0zq73nkyjw0h69fxi52t8jt37lf&ep=v1_gifs_search&rid=giphy.gif&ct=g",
    "https://i.giphy.com/26BRuo6sLetdllPAQ.webp",
    "https://i.giphy.com/tXL4FHPSnVJ0A.gif",
]
