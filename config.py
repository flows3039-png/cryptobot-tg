# config.py
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = 7162454634  # <--- Твой ID (главный админ)
BOT_USERNAME = ""

# Список валют с кастомными эмодзи
CURRENCIES = {
    "USDT": {"emoji_id": "5280846677673010353", "emoji": "💎", "name": "Tether", "price_usd": 1.0},
    "GRAM": {"emoji_id": "5265151230790884988", "emoji": "💠", "name": "Gram", "price_usd": 1.31},
    "TON":  {"emoji_id": "5265151230790884988", "emoji": "💠", "name": "Toncoin", "price_usd": 5.50},
    "SOL":  {"emoji_id": "5280476129369543392", "emoji": "🟣", "name": "Solana", "price_usd": 104.25},
    "TRX":  {"emoji_id": "5274031466517377092", "emoji": "🔴", "name": "TRON", "price_usd": 0.3294},
    "BTC":  {"emoji_id": "5280624271381520811", "emoji": "🟠", "name": "Bitcoin", "price_usd": 81002.15},
    "ETH":  {"emoji_id": "5280613443768967293", "emoji": "🔵", "name": "Ethereum", "price_usd": 2396.72},
    "DOGE": {"emoji_id": "5285358914479609357", "emoji": "🟡", "name": "Dogecoin", "price_usd": 0.07993},
    "LTC":  {"emoji_id": "5273967072072706245", "emoji": "🔷", "name": "Litecoin", "price_usd": 58.08},
    "BNB":  {"emoji_id": "5280907155107506256", "emoji": "🟡", "name": "Binance Coin", "price_usd": 746.18},
    "USDC": {"emoji_id": "5465379230286093848", "emoji": "🔵", "name": "USD Coin", "price_usd": 0.9996},
    "XAUT": {"emoji_id": "5274109686461786158", "emoji": "🟡", "name": "Tether Gold", "price_usd": 3999.51},
}

# Фиатные валюты для P2P
FIAT_CURRENCIES = [
    "RUB", "USD", "EUR", "BYN", "UAH", "KZT", "UZS", "GEL", "TRY",
    "AMD", "THB", "INR", "BRL", "IDR", "AZN", "AED", "PLN", "ILS",
    "KGS", "TJS", "LKR", "MDL"
]

FIAT_FLAGS = {
    "RUB": "🇷🇺", "USD": "🇺🇸", "EUR": "🇪🇺", "BYN": "🇧🇾", "UAH": "🇺🇦",
    "KZT": "🇰🇿", "UZS": "🇺🇿", "GEL": "🇬🇪", "TRY": "🇹🇷", "AMD": "🇦🇲",
    "THB": "🇹🇭", "INR": "🇮🇳", "BRL": "🇧🇷", "IDR": "🇮🇩", "AZN": "🇦🇿",
    "AED": "🇦🇪", "PLN": "🇵🇱", "ILS": "🇮🇱", "KGS": "🇰🇬", "TJS": "🇹🇯",
    "LKR": "🇱🇰", "MDL": "🇲🇩"
}

EMOJI = {
    "crypto": "5361914370068613491", "wallet": "5310191758255099001", "pay": "5361543877599724417",
    "gift": "5361986358015463601", "bulb": "5362084755716214813", "arrows_cycle": "5312212278374861302",
    "shop": "5361781191722699867", "cup": "5361767787129766930", "premium": "5362006552951690043",
    "unknown1": "5361692603727252420", "home_dollar": "5312419154064607942", "arrows_diff": "5361993818373655559",
    "gift_bulb": "5364047422626500018", "sbp": "5363972466857252756", "home_orange": "5312419154064607942",
    "home_green": "5312419154064607942", "megaphone": "5312161417372142817", "unknown3": "5312419154064607942",
    "arrows_cycle2": "5312212278374861302", "check_btn": "5311998535032409760", "invoice_btn": "5312043357311111246",
    "dollar": "5309795500277403547", "support": "5312365458383474419", "settings": "5309974037772928528",
    "message": "5312103894875143512", "card": "5312057711091813718", "verified": "5312326644764018054",
    "diamond_check": "5309762875705823313", "arrows_up": "5312014881677934423", "qr": "5309771942381785364",
    "danger": "5319034842514499001", "aml": "5318822061244716022", "arrow_down": "5318862055980177086",
    "arrow_up": "5319073291061730002", "ban": "5319096054388401002", "heart_broken": "5318859418870258003",
    "dislike": "5321127775782870841", "fake": "5321145226234993332", "kyc": "5319204107175631682",
    "lightning": "5318810984524060823", "like": "5319185724715606087", "minus": "5319260826513742496",
    "new": "5318817040427949274", "plus": "5318863168376709909", "premium_clean": "5319069159303194146",
    "heart_purple": "5319000753359065895", "heart_red": "5319062772686823000", "scam": "5318908072259787465",
    "leaf": "5253944419870062295"
}

def _e(key: str, fallback: str) -> str:
    emoji_id = EMOJI.get(key)
    if not emoji_id:
        return fallback
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'