import os
from typing import List, Dict, Any

from bot.data_sources.baza2 import glass_data9  # будет сгенерено


def perform_size_search(height: float, width: float) -> List[Dict[str, Any]]:
    found = []
    for glass in glass_data9:
        try:
            if float(glass.get("height")) == float(height) and float(glass.get("width")) == float(width):
                found.append({
                    "model": glass.get("model"),
                    "photo_path": glass.get("photo_path", None)
                })
        except Exception:
            continue
    return found


def photo_exists(path: str | None) -> bool:
    return bool(path and os.path.exists(path))
