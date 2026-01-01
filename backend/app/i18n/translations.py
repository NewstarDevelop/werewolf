"""i18n translation management for backend."""
import json
from pathlib import Path
from typing import Dict, Any

# Translation file directory
I18N_DIR = Path(__file__).parent

# Translation cache
_translations: Dict[str, Dict[str, Any]] = {}

SUPPORTED_LANGUAGES = {"zh", "en"}

def normalize_language(language: str) -> str:
    """
    Normalize and validate language code.

    Args:
        language: Language code to validate

    Returns:
        Validated language code ("zh" or "en"), defaults to "zh" for invalid input
    """
    if not isinstance(language, str):
        return "zh"

    language = language.strip().lower()

    # Only allow alphanumeric to prevent path traversal
    if not language.isalnum():
        return "zh"

    return language if language in SUPPORTED_LANGUAGES else "zh"

def load_translations(language: str) -> Dict[str, Any]:
    """Load translation file for specified language."""
    # Validate and normalize language
    language = normalize_language(language)

    if language not in _translations:
        file_path = I18N_DIR / f"{language}.json"
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                _translations[language] = json.load(f)
        else:
            # Fallback to Chinese
            fallback_path = I18N_DIR / "zh.json"
            if fallback_path.exists():
                with open(fallback_path, 'r', encoding='utf-8') as f:
                    _translations[language] = json.load(f)
            else:
                _translations[language] = {}
    return _translations[language]

def t(key: str, language: str = "zh", **kwargs) -> str:
    """
    Translate a key to specified language.

    Args:
        key: Translation key in dot notation (e.g., "roles.werewolf")
        language: Target language code ("zh" or "en")
        **kwargs: Interpolation variables

    Returns:
        Translated string
    """
    translations = load_translations(language)

    # Navigate nested dict using dot notation
    keys = key.split('.')
    value = translations
    for k in keys:
        if isinstance(value, dict):
            value = value.get(k, key)
        else:
            return key

    # Interpolation
    if isinstance(value, str) and kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, ValueError):
            return value
    return value if isinstance(value, str) else key
