from urllib.parse import urlparse, parse_qs
from constants import MODELS


def parse_url(url: str) -> dict:
    parsed_url = urlparse(url)
    params = parse_qs(parsed_url.query)

    data = {
        "width": int(params.get("width", [1000])[0]),
        "height": int(params.get("height", [1000])[0]),
        "model": params.get("model", [MODELS[0]])[0],
        "safe": True if params.get("safe", [False])[0] == "True" else False,
        "cached": True if "seed" not in params else False,
        "nologo": True if params.get("nologo", [False])[0] == "True" else False,
        "enhance": True if params.get("enhance", [False])[0] == "True" else False,
    }

    return data
