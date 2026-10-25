# image_gen.py
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

_cached_bg_image = None
_cached_fonts = {}

def get_cached_bg() -> Image.Image:
    global _cached_bg_image
    if _cached_bg_image is None:
        bg_path = get_bg_path()
        if bg_path and os.path.exists(bg_path):
            _cached_bg_image = Image.open(bg_path).convert("RGBA")
        else:
            _cached_bg_image = Image.new("RGBA", (1280, 800), (22, 28, 36, 255))
    return _cached_bg_image.copy()

def get_cached_font(size: int):
    global _cached_fonts
    if size not in _cached_fonts:
        font_path = get_font_path()
        if font_path and os.path.exists(font_path):
            try:
                _cached_fonts[size] = ImageFont.truetype(font_path, size)
            except Exception:
                _cached_fonts[size] = ImageFont.load_default()
        else:
            _cached_fonts[size] = ImageFont.load_default()
    return _cached_fonts[size]

def add_ticket_frame(check_bytes: bytes) -> bytes:
    """Оборачивает фото чека в купонный билетный фрейм с перфорацией и скругленными углами."""
    try:
        check_img = Image.open(io.BytesIO(check_bytes)).convert("RGBA")
        cw, ch = check_img.size

        # Отступы под рамку и перфорацию
        left_margin = int(cw * 0.055)
        right_margin = int(cw * 0.035)
        top_margin = int(ch * 0.045)
        bottom_margin = int(ch * 0.045)

        fw = cw + left_margin + right_margin
        fh = ch + top_margin + bottom_margin

        # Цвет рамки из официального скриншота: (86, 72, 117)
        frame_bg_color = (86, 72, 117, 255)
        frame = Image.new("RGBA", (fw, fh), frame_bg_color)

        # Скругляем внутренний чек
        corner_radius = int(ch * 0.035)
        mask = Image.new("L", (cw, ch), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.rounded_rectangle((0, 0, cw, ch), radius=corner_radius, fill=255)

        frame.paste(check_img, (left_margin, top_margin), mask)

        # Рисуем линию отрывной перфорации на левой планке билета
        draw = ImageDraw.Draw(frame)
        stub_x = left_margin // 2 + 4
        dash_length = int(ch * 0.02)
        gap_length = int(ch * 0.012)
        line_width = max(2, int(cw * 0.003))
        stitch_color = (130, 115, 175, 255)

        y = top_margin
        while y < fh - bottom_margin:
            draw.line([(stub_x, y), (stub_x, min(y + dash_length, fh - bottom_margin))], fill=stitch_color, width=line_width)
            y += dash_length + gap_length

        # Тонкая внутренняя обводка вокруг чека
        draw.rounded_rectangle(
            (left_margin, top_margin, left_margin + cw, top_margin + ch),
            radius=corner_radius,
            outline=(60, 50, 85, 200),
            width=max(2, int(cw * 0.002))
        )

        out_buf = io.BytesIO()
        frame.convert("RGB").save(out_buf, format="JPEG", quality=95)
        return out_buf.getvalue()
    except Exception as e:
        log.warning("add_ticket_frame failed (%s), returning original check bytes", e)
        return check_bytes

def generate_check_image_bytes(
    amount: str,
    currency: str,
    check_id: str = "",
    fiat_amount: str = "",
    creator_name: str = "Crypto Bot"
) -> bytes:
    base_image = get_cached_bg()
    draw = ImageDraw.Draw(base_image)
    image_width, image_height = base_image.size

    font_amount = get_cached_font(80)
    font_currency = get_cached_font(36)
    font_fiat = get_cached_font(30)
    font_info = get_cached_font(28)

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
    base_image.save(buf, format="PNG", optimize=False)
    return buf.getvalue()

def generate_check_image(
    amount: str,
    currency: str,
    check_id: str,
    creator_name: str = "Crypto Bot",
    output_path: str = "generated_check.png"
) -> str:
    data = generate_check_image_bytes(amount, currency, check_id=check_id, creator_name=creator_name)
    framed = add_ticket_frame(data)
    with open(output_path, "wb") as f:
        f.write(framed)
    return output_path

_http_client: httpx.AsyncClient | None = None

def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=5.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
    return _http_client

async def fetch_check_image(asset: str, amount: str, fiat_amount: str, check_id: str = "") -> bytes:
    clean_fiat = str(fiat_amount).replace("$", "").strip()
    url = f"https://imggen.cr.bot/checks/image?asset={asset}&asset_amount={amount}&fiat=USD&fiat_amount={clean_fiat}&main=asset&v5"

    try:
        client = get_http_client()
        r = await client.get(url)
        if r.status_code == 200 and len(r.content) > 1000:
            return add_ticket_frame(r.content)
        log.warning("imggen returned %s, falling back to local generator", r.status_code)
    except Exception as e:
        log.warning("imggen request failed (%s), falling back to local generator", e)

    raw_bytes = generate_check_image_bytes(amount, asset, check_id=check_id, fiat_amount=clean_fiat)
    return add_ticket_frame(raw_bytes)
