"""
receipts.py - Read a receipt photo with the Muse Spark model.

The model's only job is to READ the receipt: vendor name, date and total.
All comparisons and math happen later in plain Python (see matching.py).

To save money and time, every result is stored in a JSON cache file keyed
by the image's SHA-256 hash. The same image is never sent to the API twice.
"""

import base64
import hashlib
import json
import os
from datetime import date

from dotenv import load_dotenv

DEFAULT_CACHE_PATH = "receipt_cache.json"

# The instructions we send along with each image.
RECEIPT_PROMPT = (
    "You are reading a photo of a store receipt. "
    "Reply with ONLY a JSON object, no other text, in exactly this form:\n"
    '{"vendor": "store name", "date": "YYYY-MM-DD", "total": 12.34}\n'
    "Use the final total that was charged (including tax). "
    "The total must be a number without a currency symbol."
)


def get_muse_settings():
    """
    Read the Muse Spark settings from the environment (or the .env file).

    Returns (api_key, base_url, model). Raises a clear error if one is missing.
    """
    # load_dotenv() copies the values from the .env file into os.environ.
    load_dotenv()
    api_key = os.getenv("MUSE_API_KEY")
    base_url = os.getenv("MUSE_BASE_URL")
    model = os.getenv("MUSE_MODEL")

    missing = [name for name, value in [
        ("MUSE_API_KEY", api_key),
        ("MUSE_BASE_URL", base_url),
        ("MUSE_MODEL", model),
    ] if not value]
    if missing:
        raise RuntimeError(
            "Missing settings: " + ", ".join(missing)
            + ". Copy .env.example to .env and fill in your values."
        )
    return api_key, base_url, model


def make_client():
    """Create an OpenAI-compatible client pointed at Meta's Muse Spark API."""
    # Imported here so the rest of this file works even without the package.
    from openai import OpenAI

    api_key, base_url, _model = get_muse_settings()
    return OpenAI(api_key=api_key, base_url=base_url)


def image_hash(image_bytes):
    """Return a fingerprint (SHA-256 hex string) of the image's bytes."""
    return hashlib.sha256(image_bytes).hexdigest()


def load_cache(cache_path):
    """Load the cache dict from disk, or an empty dict if there is no file yet."""
    if not os.path.exists(cache_path):
        return {}
    with open(cache_path, encoding="utf-8") as f:
        return json.load(f)


def save_cache(cache, cache_path):
    """Write the cache dict back to disk."""
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def parse_model_json(text):
    """
    Turn the model's reply into a Python dict.

    Models sometimes wrap JSON in a ```json ... ``` code fence even when
    asked not to, so we strip that first.
    """
    text = text.strip()
    if text.startswith("```"):
        # Drop the first line (``` or ```json) and the closing ```.
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return json.loads(text)


def clean_receipt(data, filename=""):
    """
    Check and tidy the values the model gave us, using plain Python.

    Returns {"vendor": str, "date": "YYYY-MM-DD", "total": float, "file": str}.
    """
    # Remove "$" and "," in case the model added them anyway.
    total = float(str(data["total"]).replace("$", "").replace(",", ""))
    # Raises an error if the date is not in YYYY-MM-DD form.
    receipt_date = date.fromisoformat(str(data["date"]).strip())
    return {
        "vendor": str(data["vendor"]).strip(),
        "date": receipt_date.isoformat(),
        "total": round(total, 2),
        "file": filename,
    }


def read_receipt(image_path=None, image_bytes=None, filename=None,
                 client=None, model=None, cache_path=DEFAULT_CACHE_PATH):
    """
    Read one receipt image and return {"vendor", "date", "total", "file"}.

    Pass either `image_path` (a file on disk) or `image_bytes` (for example
    an uploaded file). `client` and `model` are optional; tests pass in a
    fake client so no real API calls are made.

    Note: "date" is returned as a "YYYY-MM-DD" string so it can be saved
    in the JSON cache. Use receipt_with_date() to get a real date object.
    """
    if image_bytes is None:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
    if filename is None:
        filename = os.path.basename(image_path) if image_path else ""

    # 1. Check the cache first. Same image = same hash = no API call.
    key = image_hash(image_bytes)
    cache = load_cache(cache_path)
    if key in cache:
        result = dict(cache[key])
        result["file"] = filename
        return result

    # 2. Not cached: send the image to the model.
    if client is None:
        client = make_client()
    if model is None:
        model = get_muse_settings()[2]

    # Images are sent as a "data URL": the bytes encoded as base64 text.
    b64 = base64.b64encode(image_bytes).decode("ascii")
    mime = "image/png" if filename.lower().endswith(".png") else "image/jpeg"

    response = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": RECEIPT_PROMPT},
                {"type": "image_url",
                 "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ],
        }],
    )
    reply_text = response.choices[0].message.content

    # 3. Parse and tidy the answer, then save it in the cache.
    result = clean_receipt(parse_model_json(reply_text), filename)
    cache[key] = result
    save_cache(cache, cache_path)
    return result


def receipt_with_date(receipt):
    """Return a copy of a receipt where "date" is a real date object."""
    copy = dict(receipt)
    if isinstance(copy["date"], str):
        copy["date"] = date.fromisoformat(copy["date"])
    return copy
