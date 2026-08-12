import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _parse_chat_ids(raw: str) -> set[int]:
    if not raw.strip():
        return set()
    return {int(x.strip()) for x in raw.split(",") if x.strip()}


@dataclass(frozen=True)
class Config:
    token: str
    allowed_chat_ids: set[int]
    spam_threshold: int
    log_level: str
    admin_chat_id: int


def load_config() -> Config:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не задан. Скопируйте .env.example в .env и укажите токен.")

    chat_id = os.getenv("ADMIN_CHAT_ID", "").strip()
    if not chat_id:
        raise ValueError("ADMIN_CHAT_ID не задан. Скопируйте .env.example в .env и укажите токен.")

    threshold = int(os.getenv("SPAM_THRESHOLD", "50"))
    if not 0 <= threshold <= 100:
        raise ValueError("SPAM_THRESHOLD должен быть от 0 до 100.")

    return Config(
        token=token,
        allowed_chat_ids=_parse_chat_ids(os.getenv("ALLOWED_CHAT_IDS", "")),
        spam_threshold=threshold,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        admin_chat_id=chat_id,
    )
