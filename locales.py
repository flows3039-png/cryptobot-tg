# locales.py
STRINGS = {
    "ru": {
        "main_menu": "Главное меню",
        "wallet": "Кошелёк",
        "settings": "Настройки профиля",
        "profile_text": "👤 <b>Настройки профиля</b>\n\nЗдесь вы можете настроить уведомления, валюту, часовой пояс и другие параметры.",
        "tz_choose": "🌍 <b>Выберите ваш часовой пояс:</b>",
        "tz_changed": "✅ <b>Часовой пояс изменён на {tz}</b>",
        "lang_choose": "🇷🇺 <b>Выберите язык бота:</b>",
        "lang_changed": "✅ <b>Язык изменён на Русский</b>",
        "back": "‹ Назад",
        "settings_saved": "Настройки сохранены!",
        "exchange_dev": "🐬 <b>Биржа</b>\n\nФункция обмена в разработке.",
        "subs_dev": "🎁 <b>Счета и Розыгрыши</b>\n\nРаздел в разработке.",
        "ref_text": "👥 <b>Рефералы</b>\n\nЗдесь будет ваша ссылка.",
        "pay_text": "💳 <b>Crypto Pay</b>\n\nИнтеграция платежной системы.",
        "contests_text": "🏅 <b>Конкурсы и Активности</b>\n\nВ данный момент активных конкурсов нет.\n\nСледите за обновлениями в нашем <a href=\"https://t.me/CryptoBotRU\">официальном канале</a>!"
    },
    "en": {
        "main_menu": "Main Menu",
        "wallet": "Wallet",
        "settings": "Profile Settings",
        "profile_text": "👤 <b>Profile Settings</b>\n\nHere you can configure notifications, currency, timezone, and other parameters.",
        "tz_choose": "🌍 <b>Select your timezone:</b>",
        "tz_changed": "✅ <b>Timezone changed to {tz}</b>",
        "lang_choose": "🇬🇧 <b>Select bot language:</b>",
        "lang_changed": "✅ <b>Language changed to English</b>",
        "back": "‹ Back",
        "settings_saved": "Settings saved!",
        "exchange_dev": "🐬 <b>Exchange</b>\n\nExchange feature is under development.",
        "subs_dev": "🎁 <b>Invoices & Giveaways</b>\n\nSection under development.",
        "ref_text": "👥 <b>Referrals</b>\n\nYour referral link will be here.",
        "pay_text": "💳 <b>Crypto Pay</b>\n\nPayment system integration.",
        "contests_text": "🏅 <b>Contests & Activities</b>\n\nThere are no active contests at the moment.\n\nFollow our <a href=\"https://t.me/CryptoBotRU\">official channel</a>!"
    }
}

def t(lang: str, key: str, **kwargs) -> str:
    text = STRINGS.get(lang, STRINGS["ru"]).get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text