# This file is part of SafeTool Pix, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""
Internationalization (i18n) system for SafeTool Pix.

Provides a lightweight JSON-based translation system with a universal tr() function
usable everywhere (UI + services, no PyQt6 dependency).

Usage:
    from utils.i18n import tr, init_i18n

    # Initialize at app startup (once)
    init_i18n("es")  # or "en"

    # Use tr() anywhere
    label = tr("common.cancel")  # "Cancelar" / "Cancel"
    msg = tr("formats.files_count", count=42)  # "42 archivos" / "42 files"
"""
import json
from pathlib import Path
from typing import Any, Dict, Optional


# Supported languages: code -> native name
SUPPORTED_LANGUAGES: Dict[str, str] = {
    "es": "Español",
    "en": "English",
}

DEFAULT_LANGUAGE = "es"

# Module-level state (read-only after init, thread-safe)
_translations: Dict[str, Any] = {}
_fallback: Dict[str, Any] = {}
_current_lang: str = DEFAULT_LANGUAGE
_initialized: bool = False

# Directory where i18n JSON files are stored
_I18N_DIR = Path(__file__).resolve().parent.parent / "i18n"


def _resolve_key(data: Dict[str, Any], key: str) -> Optional[str]:
    """
    Resolve a dotted key (e.g. 'tools.zero_byte.title') against a nested dict.

    Returns the string value or None if not found.
    """
    parts = key.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current if isinstance(current, str) else None


def _load_language_file(lang: str) -> Dict[str, Any]:
    """Load a JSON translation file for the given language code."""
    file_path = _I18N_DIR / f"{lang}.json"
    if not file_path.exists():
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def init_i18n(lang: str = DEFAULT_LANGUAGE) -> None:
    """
    Initialize the i18n system with the given language.

    Must be called once at application startup, before any tr() calls.
    Always loads Spanish as fallback to guarantee no empty UI strings.

    Args:
        lang: Language code ('es', 'en'). Defaults to 'es'.
    """
    global _translations, _fallback, _current_lang, _initialized

    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE

    _current_lang = lang
    _fallback = _load_language_file(DEFAULT_LANGUAGE)

    if lang == DEFAULT_LANGUAGE:
        _translations = _fallback
    else:
        _translations = _load_language_file(lang)

    _initialized = True


def tr(key: str, **kwargs: Any) -> str:
    """
    Translate a key to the current language.

    Resolution order:
    1. Current language translations
    2. Spanish fallback
    3. The key itself (as last resort)

    Supports str.format() interpolation with **kwargs:
        tr("formats.files_count", count=42) -> "42 archivos"

    Args:
        key: Dotted translation key (e.g. 'common.cancel', 'tools.zero_byte.title')
        **kwargs: Format parameters for string interpolation

    Returns:
        Translated string, or fallback, or the key if not found
    """
    if not _initialized:
        # Auto-initialize with default language if not done yet
        init_i18n(DEFAULT_LANGUAGE)

    # Try current language first
    value = _resolve_key(_translations, key)

    # Fall back to Spanish
    if value is None and _translations is not _fallback:
        value = _resolve_key(_fallback, key)

    # Last resort: return the key itself
    if value is None:
        return key

    # Apply format interpolation if kwargs provided
    if kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return value

    return value


def get_current_language() -> str:
    """Return the current language code."""
    return _current_lang


def get_supported_languages() -> Dict[str, str]:
    """Return dict of supported language codes to native names."""
    return SUPPORTED_LANGUAGES.copy()
