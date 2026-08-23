"""
Telegram Custom/Premium Emoji Helper Module

This module manages custom emoji mapping and provides helpers to format message
text using Telegram's custom_emoji MessageEntity mechanism (both via HTML <tg-emoji>
tags and via telebot.types.MessageEntity objects).

Custom Emoji ID Mappings:
  🛒 = 5803157955482227929
  📦 = 5458790973792340888
  💰 = 5785325680765965100
  🔍 = 4958587679361991667
  📣 = 6095891759462617671
  📢 = 6095891759462617671 (maps to 📣 custom emoji ID)
  💬 = 6095865895169560113
  ⚠️ = 6089079808187174973
  ➕ = 6093406373557571574
"""

import re
from typing import Dict, List, Optional, Any

try:
    import telebot.types
except ImportError:
    telebot = None

# Exact custom emoji mappings
CUSTOM_EMOJIS: Dict[str, str] = {
    "🛒": "5803157955482227929",
    "📦": "5458790973792340888",
    "💰": "5785325680765965100",
    "🔍": "4958587679361991667",
    "📣": "6095891759462617671",
    "📢": "6095891759462617671",
    "💬": "6095865895169560113",
    "⚠️": "6089079808187174973",
    "➕": "6093406373557571574",
}


def get_custom_emoji_id(emoji_char: str) -> Optional[str]:
    """Return custom emoji ID for a given emoji character, or None."""
    return CUSTOM_EMOJIS.get(emoji_char)


def custom_emoji_html(emoji_char: str) -> str:
    """
    Return Telegram HTML <tg-emoji> tag for the custom emoji.
    Keeps the original Unicode emoji inside the tag as fallback.
    """
    emoji_id = CUSTOM_EMOJIS.get(emoji_char)
    if emoji_id:
        return f'<tg-emoji emoji-id="{emoji_id}">{emoji_char}</tg-emoji>'
    return emoji_char


def apply_custom_emojis(text: str) -> str:
    """
    Scan text and replace mapped Unicode emojis with <tg-emoji> HTML tags.
    Does not replace emojis that are already inside a <tg-emoji> tag or attribute.
    """
    if not text:
        return text

    # Pattern to match existing tags or our mapped emojis
    # We sort by length descending to match composite sequences if any
    sorted_emojis = sorted(CUSTOM_EMOJIS.keys(), key=len, reverse=True)
    emoji_pattern = "|".join(re.escape(e) for e in sorted_emojis)
    
    # Match either an existing tag/tg-emoji or an emoji character
    token_pattern = re.compile(rf'(<tg-emoji[^>]*>.*?</tg-emoji>|<[^>]+>)|({emoji_pattern})', re.DOTALL)

    def replace_match(match):
        existing_tag, emoji_match = match.groups()
        if existing_tag:
            return existing_tag
        if emoji_match:
            emoji_id = CUSTOM_EMOJIS.get(emoji_match)
            if emoji_id:
                return f'<tg-emoji emoji-id="{emoji_id}">{emoji_match}</tg-emoji>'
            return emoji_match
        return match.group(0)

    return token_pattern.sub(replace_match, text)


def get_utf16_length(s: str) -> int:
    """Return length of string in UTF-16 code units (as required by Telegram Bot API)."""
    return len(s.encode('utf-16-le')) // 2


def create_custom_emoji_entities(plain_text: str) -> List[Any]:
    """
    Scan plain_text and build a list of telebot.types.MessageEntity for Telegram API,
    calculating UTF-16 offsets and lengths correctly.
    """
    entities = []
    if not plain_text:
        return entities

    sorted_emojis = sorted(CUSTOM_EMOJIS.keys(), key=len, reverse=True)
    emoji_pattern = re.compile("|".join(re.escape(e) for e in sorted_emojis))

    # Class for entity if telebot is not imported
    EntityClass = getattr(getattr(telebot, "types", None), "MessageEntity", None)

    # Iterate through characters tracking UTF-16 offset
    current_utf16_offset = 0
    i = 0
    while i < len(plain_text):
        match = emoji_pattern.match(plain_text, i)
        if match:
            matched_emoji = match.group(0)
            emoji_id = CUSTOM_EMOJIS[matched_emoji]
            utf16_len = get_utf16_length(matched_emoji)
            if EntityClass:
                entity = EntityClass(
                    type="custom_emoji",
                    offset=current_utf16_offset,
                    length=utf16_len,
                    custom_emoji_id=emoji_id,
                )
            else:
                entity = {
                    "type": "custom_emoji",
                    "offset": current_utf16_offset,
                    "length": utf16_len,
                    "custom_emoji_id": emoji_id,
                }
            entities.append(entity)
            current_utf16_offset += utf16_len
            i += len(matched_emoji)
        else:
            char = plain_text[i]
            current_utf16_offset += get_utf16_length(char)
            i += 1

    return entities
