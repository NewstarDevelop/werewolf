"""Analysis cache service - avoid duplicate analysis."""
import json
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_cache_dir() -> Path:
    """Get cache directory path based on DATA_DIR setting.

    T-STAB-003 Fix: Lazy directory creation to support read-only environments.
    Returns the path without creating it - creation happens on write.
    """
    return Path(settings.DATA_DIR) / "analysis_cache"


def _ensure_cache_dir() -> bool:
    """Lazily create cache directory if needed.

    Returns:
        True if directory exists or was created, False if creation failed.
    """
    cache_dir = _get_cache_dir()
    if cache_dir.exists():
        return True

    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        return True
    except (OSError, PermissionError) as e:
        logger.warning(f"Cannot create cache directory {cache_dir}: {e}")
        return False


class AnalysisCache:
    """Cache for game analysis results."""

    @staticmethod
    def _get_cache_key(game_id: str, mode: str, language: str) -> str:
        """Generate cache key from game parameters.

        P2-1 Fix: Use SHA256 instead of MD5 for better practice.
        """
        key_string = f"{game_id}_{mode}_{language}"
        return hashlib.sha256(key_string.encode()).hexdigest()[:32]

    @staticmethod
    def _get_cache_path(cache_key: str) -> Path:
        """Get file path for cache key."""
        return _get_cache_dir() / f"{cache_key}.json"

    @staticmethod
    def get(game_id: str, mode: str, language: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached analysis if available."""

        cache_key = AnalysisCache._get_cache_key(game_id, mode, language)
        cache_path = AnalysisCache._get_cache_path(cache_key)

        if not cache_path.exists():
            logger.debug(f"Cache miss for {game_id}")
            return None

        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            logger.info(f"Cache hit for {game_id} (mode={mode}, lang={language})")
            return data

        except Exception as e:
            logger.warning(f"Failed to read cache: {e}")
            return None

    @staticmethod
    def set(game_id: str, mode: str, language: str, analysis_result: Dict[str, Any]) -> bool:
        """Save analysis result to cache.

        T-STAB-003 Fix: Lazily create cache directory on first write.
        Gracefully degrades if directory cannot be created.
        """
        # Ensure cache directory exists before writing
        if not _ensure_cache_dir():
            logger.warning(f"Cache disabled: cannot create directory for {game_id}")
            return False

        cache_key = AnalysisCache._get_cache_key(game_id, mode, language)
        cache_path = AnalysisCache._get_cache_path(cache_key)

        try:
            # Add metadata
            cache_data = {
                "cached_at": datetime.now().isoformat(),
                "game_id": game_id,
                "mode": mode,
                "language": language,
                "result": analysis_result
            }

            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Cached analysis for {game_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
            return False

    @staticmethod
    def clear(game_id: Optional[str] = None) -> int:
        """Clear cache for specific game or all games."""
        cache_dir = _get_cache_dir()

        # If cache directory doesn't exist, nothing to clear
        if not cache_dir.exists():
            return 0

        if game_id:
            # Clear specific game (all modes/languages)
            count = 0
            for cache_file in cache_dir.glob("*.json"):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if data.get("game_id") == game_id:
                        cache_file.unlink()
                        count += 1
                except:
                    pass
            logger.info(f"Cleared {count} cache entries for {game_id}")
            return count
        else:
            # Clear all
            count = len(list(cache_dir.glob("*.json")))
            for cache_file in cache_dir.glob("*.json"):
                cache_file.unlink()
            logger.info(f"Cleared all {count} cache entries")
            return count
