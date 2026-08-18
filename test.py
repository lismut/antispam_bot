#!/usr/bin/env python3
"""Telegram-бот: детекция спама, удаление сообщений, бан отправителей."""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone



from config import load_config
from spam_detector import SpamDetector

logger = logging.getLogger(__name__)


def setup_logging(level: str) -> None:
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        level=getattr(logging, level, logging.INFO),
        filename="bot.log",
        encoding="utf-8",
    )


def check() -> None:
    text = "Куплю USDT"

    detector = SpamDetector(50)
    verdict = detector.analyze(
        text,
        has_forward=False,
        is_new_member=False,
        username="",
    )

    if not verdict.is_spam:
        print("not spam")
        return

    logger.info(
        "Спам от user_id=%s (@%s) в chat_id=%s score=%s reasons=%s",
        "test",
        "test",
        "test",
        verdict.score,
        verdict.reasons,
    )
    print(
            f"🚫 Удалено спам-сообщение от TEST.\n"
            f"Пользователь TEST.\n"
            f"Причина: TEST"
        )
    


def main() -> None:
    cfg = load_config()

    detector = SpamDetector(threshold=cfg.spam_threshold)

    check()


    logger.info("Бот запущен. Порог спама: %s", cfg.spam_threshold)
    if cfg.allowed_chat_ids:
        logger.info("Whitelist чатов: %s", cfg.allowed_chat_ids)

    

if __name__ == "__main__":
    main()
