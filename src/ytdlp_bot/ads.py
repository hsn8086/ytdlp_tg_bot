import json
import logging
import random
import os
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)


class AdManager:
    def __init__(self, data_dir: Path):
        self.ad_file = data_dir / "ad.json"
        self._last_mtime = 0.0
        self._config = {"max_ads_per_message": 0, "ads": []}
        self._load_if_changed()

    def _load_if_changed(self):
        if not self.ad_file.exists():
            return

        current_mtime = os.path.getmtime(self.ad_file)
        if current_mtime > self._last_mtime:
            try:
                with open(self.ad_file, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
                self._last_mtime = current_mtime
                logger.info("Loaded ad configuration from %s", self.ad_file)
            except Exception as e:
                logger.error("Failed to load ad configuration: %s", e)

    def get_ads(self) -> List[Dict[str, str]]:
        self._load_if_changed()

        selected_ads = []
        ads_list = self._config.get("ads", [])
        if isinstance(ads_list, list):
            for ad in ads_list:
                if isinstance(ad, dict) and random.random() < ad.get("probability", 0):
                    selected_ads.append({"title": ad["title"], "url": ad["url"]})

        max_ads = self._config.get("max_ads_per_message", 0)
        if isinstance(max_ads, int) and max_ads > 0 and len(selected_ads) > max_ads:
            selected_ads = random.sample(selected_ads, max_ads)

        return selected_ads
