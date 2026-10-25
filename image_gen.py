import os
import io
import time
import logging
import httpx
from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("check_image")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _find_file(filename: str, candidates: list[str]) -> str | None:
    for path in candidates:
        full_path = os.path.abspath(os.path.join(BASE_DIR, path))
        if os.path.exists(full_path):
            return full_path
    return None

def get_bg_path() -> str | None:
    return _find_file("check_bg.png", [
        "check_bg.png",
        os.path.join("assets", "check_bg.png"),
    ])

def get_font_path() -> str | None:
    return _find_file("font", [
        os.path.join("assets", "fonts", "SFProDisplay-Medium.ttf"),
        "sf-pro-rounded-medium.otf",
        os.path.join("assets", "SFProDisplay-Medium.ttf"),
    ])

def generate_check_image_bytes(
    amount: str,
    currency: str,
    check_id: str = "",
    fiat_amount: str = "",
    creator_name: str = "Crypto Bot"
) -> bytes:
    bg_path = get_bg_path()
    if bg_path and os.path.exists(bg_path):
        base_image = Image.open(bg_path).convert("RGBA")
    else:
        # Fallback canvas if background template is absent
        base_image = Image.new("RGBA", (1280, 800), (22, 28, 36, 255))

    draw = ImageDraw.Draw(base_image)
    image_width, image_height = base_image.size

    font_path = get_font_path()
    if font_path:
        font_amount = ImageFont.truetype(font_path, 80)
        font_currency = ImageFont.truetype(font_path, 36)
        font_fiat = ImageFont.truetype(font_path, 30)
        font_info = ImageFont.truetype(font_path, 28)
    else:
        font_amount = ImageFont.load_default()
        font_currency = ImageFont.load_default()
        font_fiat = ImageFont.load_default()
        font_info = ImageFont.load_default()

    color_primary = (255, 255, 255, 255)
    color_secondary = (160, 163, 189, 255)
    color_accent = (0, 152, 234, 255)

    # 1. Сумма и валюта
    main_text = f"{amount} {currency.upper()}"
    bbox_main = draw.textbbox((0, 0), main_text, font=font_amount)
    w_main = bbox_main[2] - bbox_main[0]
    center_y = image_height // 2 - 60
    draw.text(((image_width - w_main) / 2, center_y), main_text, font=font_amount, fill=color_primary)

    # 2. Фиатный эквивалент
    if fiat_amount:
        fiat_display = f"≈ ${fiat_amount}" if not fiat_amount.startswith("$") else f"≈ {fiat_amount}"
        bbox_fiat = draw.textbbox((0, 0), fiat_display, font=font_fiat)
        w_fiat = bbox_fiat[2] - bbox_fiat[0]
        draw.text(((image_width - w_fiat) / 2, center_y + 100), fiat_display, font=font_fiat, fill=color_secondary)

    # 3. Инфо блок внизу
    if check_id:
        id_text = f"#{check_id}"
        bbox_id = draw.textbbox((0, 0), id_text, font=font_info)
        draw.text(((image_width - (bbox_id[2] - bbox_id[0])) / 2, image_height - 120), id_text, font=font_info, fill=color_accent)

    buf = io.BytesIO()
    base_image.save(buf, format="PNG")
    return buf.getvalue()

def generate_check_image(
    amount: str,
    currency: str,
    check_id: str,
    creator_name: str = "Crypto Bot",
    output_path: str = "generated_check.png"
) -> str:
    data = generate_check_image_bytes(amount, currency, check_id=check_id, creator_name=creator_name)
    with open(output_path, "wb") as f:
        f.write(data)
    return output_path

async def fetch_check_image(asset: str, amount: str, fiat_amount: str, check_id: str = "") -> bytes:
    params = {
        "asset": asset,
        "asset_amount": amount,
        "fiat": "USD",
        "fiat_amount": fiat_amount,
        "main": "asset",
        "v5": "",
        "_": int(time.time() * 1000),
    }
    try:
        async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
            r = await client.get("https://imggen.cr.bot/checks/image", params=params)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
                return r.content
            log.warning("imggen returned status %s / %s, falling back to local generator", r.status_code, r.headers.get("content-type"))
    except Exception as e:
        log.warning("imggen request failed (%s), falling back to local generator", e)

    return generate_check_image_bytes(amount, asset, check_id=check_id, fiat_amount=fiat_amount)
