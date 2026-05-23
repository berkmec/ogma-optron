"""Quick sanity test for Qwen2-VL via HuggingFace Inference Providers (router).

Sends a small image + prompt and prints the model's response.

Usage:
    1. Copy .env.example to .env and fill HF_TOKEN
    2. python scripts/sanity_qwen_vl.py [path/to/image.png]

If no image path is given, an 8x8 red square is generated in-memory.
"""

from __future__ import annotations

import base64
import os
import sys
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image

load_dotenv()

HF_TOKEN = os.environ.get("HF_TOKEN", "")
VISION_MODEL = os.environ.get("VISION_MODEL", "Qwen/Qwen2-VL-7B-Instruct")
BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://router.huggingface.co/v1")


def image_to_data_url(path: Path | None) -> str:
    if path is None:
        img = Image.new("RGB", (8, 8), color=(220, 60, 60))
        buf = BytesIO()
        img.save(buf, format="PNG")
        raw = buf.getvalue()
        suffix = "png"
    else:
        raw = path.read_bytes()
        suffix = (path.suffix.lower().lstrip(".") or "png")
        if suffix == "jpg":
            suffix = "jpeg"
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/{suffix};base64,{b64}"


def main() -> None:
    if not HF_TOKEN or HF_TOKEN.startswith("hf_your"):
        sys.exit(
            "ERROR: HF_TOKEN not set in .env. "
            "Get one at https://huggingface.co/settings/tokens (Read access is enough)."
        )

    img_path: Path | None = None
    if len(sys.argv) > 1:
        img_path = Path(sys.argv[1])
        if not img_path.exists():
            sys.exit(f"Image not found: {img_path}")

    client = OpenAI(base_url=BASE_URL, api_key=HF_TOKEN)
    data_url = image_to_data_url(img_path)

    print(f"Model     : {VISION_MODEL}")
    print(f"Base URL  : {BASE_URL}")
    print(f"Image     : {'in-memory 8x8 red square' if img_path is None else img_path}")
    print("Sending request...")

    response = client.chat.completions.create(
        model=VISION_MODEL,
        max_tokens=256,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Describe this image in 1-2 sentences. If it contains text, transcribe it.",
                    },
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    )

    print("\n--- Response ---")
    print(response.choices[0].message.content)
    print("---")
    usage = getattr(response, "usage", None)
    if usage is not None:
        print(
            f"Tokens: prompt={usage.prompt_tokens}, "
            f"completion={usage.completion_tokens}"
        )


if __name__ == "__main__":
    main()
