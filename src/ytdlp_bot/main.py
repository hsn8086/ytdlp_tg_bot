from __future__ import annotations

import logging

from ytdlp_bot.bot import VideoBot
from ytdlp_bot.config import load_settings


def main() -> None:
    settings = load_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    bot = VideoBot(settings)
    bot.run()


if __name__ == "__main__":
    main()
