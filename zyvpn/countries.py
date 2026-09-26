import re
from typing import Tuple, Optional

# Emoji to ISO Alpha-2
def emoji_to_country_code(emoji: str) -> Optional[str]:
    """Convert Unicode flag emoji to 2-letter ISO code."""
    if len(emoji) == 2:
        c1 = ord(emoji[0]) - 0x1F1E6
        c2 = ord(emoji[1]) - 0x1F1E6
        if 0 <= c1 <= 25 and 0 <= c2 <= 25:
            return chr(c1 + ord('A')) + chr(c2 + ord('A'))
    return None

def country_code_to_emoji(code: str) -> str:
    """Convert 2-letter ISO code to Unicode flag emoji."""
    if len(code) == 2 and code.isalpha():
        code = code.upper()
        return chr(ord(code[0]) - ord('A') + 0x1F1E6) + chr(ord(code[1]) - ord('A') + 0x1F1E6)
    return "🌐"

# Known country mappings (English, Russian, variations)
COUNTRY_MAP = {
    "SE": {"code": "se", "name_en": "Sweden", "name_ru": "Швеция", "flag": "🇸🇪"},
    "FR": {"code": "fr", "name_en": "France", "name_ru": "Франция", "flag": "🇫🇷"},
    "GB": {"code": "gb", "name_en": "United Kingdom", "name_ru": "Великобритания", "flag": "🇬🇧"},
    "DE": {"code": "de", "name_en": "Germany", "name_ru": "Германия", "flag": "🇩🇪"},
    "US": {"code": "us", "name_en": "United States", "name_ru": "США", "flag": "🇺🇸"},
    "RU": {"code": "ru", "name_en": "Russia", "name_ru": "Россия", "flag": "🇷🇺"},
    "NL": {"code": "nl", "name_en": "Netherlands", "name_ru": "Нидерланды", "flag": "🇳🇱"},
    "CH": {"code": "ch", "name_en": "Switzerland", "name_ru": "Швейцария", "flag": "🇨🇭"},
    "CZ": {"code": "cz", "name_en": "Czech Republic", "name_ru": "Чехия", "flag": "🇨🇿"},
    "AT": {"code": "at", "name_en": "Austria", "name_ru": "Австрия", "flag": "🇦🇹"},
    "NO": {"code": "no", "name_en": "Norway", "name_ru": "Норвегия", "flag": "🇳🇴"},
    "AL": {"code": "al", "name_en": "Albania", "name_ru": "Албания", "flag": "🇦🇱"},
    "BY": {"code": "by", "name_en": "Belarus", "name_ru": "Беларусь", "flag": "🇧🇾"},
    "GR": {"code": "gr", "name_en": "Greece", "name_ru": "Греция", "flag": "🇬🇷"},
    "LT": {"code": "lt", "name_en": "Lithuania", "name_ru": "Литва", "flag": "🇱🇹"},
    "BA": {"code": "ba", "name_en": "Bosnia and Herzegovina", "name_ru": "Босния и Герцеговина", "flag": "🇧🇦"},
    "FI": {"code": "fi", "name_en": "Finland", "name_ru": "Финляндия", "flag": "🇫🇮"},
    "PL": {"code": "pl", "name_en": "Poland", "name_ru": "Польша", "flag": "🇵🇱"},
    "TR": {"code": "tr", "name_en": "Turkey", "name_ru": "Турция", "flag": "🇹🇷"},
    "KZ": {"code": "kz", "name_en": "Kazakhstan", "name_ru": "Казахстан", "flag": "🇰🇿"},
    "SG": {"code": "sg", "name_en": "Singapore", "name_ru": "Сингапур", "flag": "🇸🇬"},
    "JP": {"code": "jp", "name_en": "Japan", "name_ru": "Япония", "flag": "🇯🇵"},
    "CA": {"code": "ca", "name_en": "Canada", "name_ru": "Канада", "flag": "🇨🇦"},
    "IT": {"code": "it", "name_en": "Italy", "name_ru": "Италия", "flag": "🇮🇹"},
    "ES": {"code": "es", "name_en": "Spain", "name_ru": "Испания", "flag": "🇪🇸"},
    "RO": {"code": "ro", "name_en": "Romania", "name_ru": "Румыния", "flag": "🇷🇴"},
    "CY": {"code": "cy", "name_en": "Cyprus", "name_ru": "Кипр", "flag": "🇨🇾"},
    "BG": {"code": "bg", "name_en": "Bulgaria", "name_ru": "Болгария", "flag": "🇧🇬"},
    "BR": {"code": "br", "name_en": "Brazil", "name_ru": "Бразилия", "flag": "🇧🇷"},
    "DK": {"code": "dk", "name_en": "Denmark", "name_ru": "Дания", "flag": "🇩🇰"},
    "HK": {"code": "hk", "name_en": "Hong Kong", "name_ru": "Гонконг", "flag": "🇭🇰"},
    "HU": {"code": "hu", "name_en": "Hungary", "name_ru": "Венгрия", "flag": "🇭🇺"},
    "ID": {"code": "id", "name_en": "Indonesia", "name_ru": "Индонезия", "flag": "🇮🇩"},
    "IN": {"code": "in", "name_en": "India", "name_ru": "Индия", "flag": "🇮🇳"},
    "MK": {"code": "mk", "name_en": "North Macedonia", "name_ru": "Северная Македония", "flag": "🇲🇰"},
    "PT": {"code": "pt", "name_en": "Portugal", "name_ru": "Португалия", "flag": "🇵🇹"},
    "RS": {"code": "rs", "name_en": "Serbia", "name_ru": "Сербия", "flag": "🇷🇸"},
    "TH": {"code": "th", "name_en": "Thailand", "name_ru": "Таиланд", "flag": "🇹🇭"},
    "UA": {"code": "ua", "name_en": "Ukraine", "name_ru": "Украина", "flag": "🇺🇦"},
    "UZ": {"code": "uz", "name_en": "Uzbekistan", "name_ru": "Узбекистан", "flag": "🇺🇿"},
    "VN": {"code": "vn", "name_en": "Vietnam", "name_ru": "Вьетнам", "flag": "🇻🇳"},
    "ZA": {"code": "za", "name_en": "South Africa", "name_ru": "ЮАР", "flag": "🇿🇦"},
    "AM": {"code": "am", "name_en": "Armenia", "name_ru": "Армения", "flag": "🇦🇲"},
    "AZ": {"code": "az", "name_en": "Azerbaijan", "name_ru": "Азербайджан", "flag": "🇦🇿"},
    "GE": {"code": "ge", "name_en": "Georgia", "name_ru": "Грузия", "flag": "🇬🇪"},
    "EE": {"code": "ee", "name_en": "Estonia", "name_ru": "Эстония", "flag": "🇪🇪"},
    "LV": {"code": "lv", "name_en": "Latvia", "name_ru": "Латвия", "flag": "🇱🇻"},
    "MD": {"code": "md", "name_en": "Moldova", "name_ru": "Молдова", "flag": "🇲🇩"},
}

# Regex to detect flag emoji: two regional indicator symbols
EMOJI_FLAG_REGEX = re.compile(r'[\U0001F1E6-\U0001F1FF]{2}')

# Keywords lookup
KEYWORD_TO_CODE = {}
for code, info in COUNTRY_MAP.items():
    KEYWORD_TO_CODE[code.lower()] = code
    KEYWORD_TO_CODE[info["name_en"].lower()] = code
    KEYWORD_TO_CODE[info["name_ru"].lower()] = code

# Additional common aliases
ALIASES = {
    "uk": "GB",
    "england": "GB",
    "great britain": "GB",
    "britain": "GB",
    "united states of america": "US",
    "usa": "US",
    "czech": "CZ",
    "czechia": "CZ",
    "saint petersburg": "RU",
    "spb": "RU",
    "novosibirsk": "RU",
    "moscow": "RU",
    "санкт-петербург": "RU",
    "спб": "RU",
    "новосибирск": "RU",
    "москва": "RU",
    "босния": "BA",
    "швейцария": "CH",
    "швеция": "SE",
}
for k, v in ALIASES.items():
    KEYWORD_TO_CODE[k.lower()] = v

def detect_country(raw_name: str) -> Tuple[str, str, str, str]:
    """
    Detect country information from node name.
    Returns: (country_name, country_code, flag_emoji, cleaned_display_name)
    """
    if not raw_name:
        return ("Unknown", "un", "🌐", "VPN Node")

    cleaned_name = raw_name.strip()
    # Strip leading [0-9]+ prefix if present: e.g. "[14] 🇸🇪 Sweden | vless | xhttp"
    cleaned_name = re.sub(r'^\[\d+\]\s*', '', cleaned_name)

    # 1. Check for emoji flag in string
    flag_match = EMOJI_FLAG_REGEX.search(cleaned_name)
    found_code = None
    if flag_match:
        emoji = flag_match.group(0)
        found_code = emoji_to_country_code(emoji)

    # 2. If no emoji flag, check for country keywords in name
    if not found_code:
        lower_name = cleaned_name.lower()
        # Sort keywords by length descending to match multi-word first ("united kingdom" before "uk")
        for kw in sorted(KEYWORD_TO_CODE.keys(), key=lambda x: -len(x)):
            # Word boundary search
            pattern = r'(?<![a-zA-Zа-яА-ЯёЁ])' + re.escape(kw) + r'(?![a-zA-Zа-яА-ЯёЁ])'
            if re.search(pattern, lower_name):
                found_code = KEYWORD_TO_CODE[kw]
                break

    if found_code and found_code.upper() in COUNTRY_MAP:
        info = COUNTRY_MAP[found_code.upper()]
        country_name = info["name_en"]
        country_code = info["code"].lower()
        flag_emoji = info["flag"]
    elif found_code:
        country_name = found_code.upper()
        country_code = found_code.lower()
        flag_emoji = country_code_to_emoji(found_code)
    else:
        country_name = "Global"
        country_code = "un"
        flag_emoji = "🌐"

    # Produce clean display name: e.g. "Sweden" or "Russia, Saint Petersburg"
    # Remove protocol badges from name: "| vless | xhttp", "| GRPC", etc.
    display_name = re.sub(r'\|\s*(vless|vmess|trojan|ss|grpc|xhttp|tcp|ws|splithttp)\s*', '', cleaned_name, flags=re.IGNORECASE)
    # Remove emoji flags from display name so the flag icon is not duplicated
    display_name = EMOJI_FLAG_REGEX.sub('', display_name).strip()
    # Remove trailing/leading pipes and spaces
    display_name = re.sub(r'^[\|\s\-\:]+|[\|\s\-\:]+$', '', display_name).strip()
    if not display_name:
        display_name = country_name

    return (country_name, country_code, flag_emoji, display_name)

def get_country_details(code: str) -> dict:
    """Return dictionary with Russian & English country names, flag emoji and flag image path."""
    code_up = (code or "un").upper()
    info = COUNTRY_MAP.get(code_up, {})
    name_ru = info.get("name_ru", code_up)
    name_en = info.get("name_en", code_up)
    flag = info.get("flag", country_code_to_emoji(code_up) if len(code_up) == 2 else "🌐")
    flag_file = f"flags/{code.lower()}.png"
    return {
        "country_code": code.lower(),
        "name_ru": name_ru,
        "name_en": name_en,
        "flag_emoji": flag,
        "flag_url": flag_file
    }
