#!/usr/bin/env python3
"""Telegram-бот: детекция спама, удаление сообщений, бан отправителей."""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone

from telegram import ChatMemberAdministrator, ChatMemberOwner, Update
from telegram.constants import ChatType, ParseMode
from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

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


async def is_bot_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)
    if isinstance(bot_member, (ChatMemberOwner, ChatMemberAdministrator)):
        if isinstance(bot_member, ChatMemberAdministrator):
            return bool(bot_member.can_delete_messages and bot_member.can_restrict_members)
        return True
    return False


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я антиспам-бот для групповых чатов.\n\n"
        "Добавьте меня в группу и назначьте администратором с правами:\n"
        "• удаление сообщений\n"
        "• блокировка участников\n\n"
        "Команды:\n"
        "/status — проверка прав и настроек\n"
        "/chatid — узнать ID текущего чата"
    )


async def cmd_chatid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    lines = [f"Chat ID: `{chat.id}`", f"Chat type: {chat.type}"]
    if user:
        lines.append(f"Your user ID: `{user.id}`")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    cfg = context.bot_data["config"]
    admin = await is_bot_admin(update, context)
    threshold = cfg.spam_threshold
    allowed = cfg.allowed_chat_ids
    chat_allowed = not allowed or chat.id in allowed

    text = (
        f"*Статус бота в этом чате*\n\n"
        f"Chat ID: `{chat.id}`\n"
        f"Права администратора: {'✅' if admin else '❌'}\n"
        f"Чат в whitelist: {'✅' if chat_allowed else '❌'}\n"
        f"Порог спама: {threshold}/100"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    cfg = context.bot_data["config"]
    if cfg.allowed_chat_ids and chat.id not in cfg.allowed_chat_ids:
        return

    if user.is_bot:
        return

    if message.entities:
        for entity in message.entities:
            if entity.type == "text_link":
                # Добавляем скрытую ссылку к тексту
                text += f" {entity.url}"
    
    # Для caption тоже проверяем entities
    if message.caption_entities:
        for entity in message.caption_entities:
            if entity.type == "text_link":
                text += f" {entity.url}"

    # Не трогаем администраторов и создателя чата
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status in ("administrator", "creator"):
            return
    except TelegramError as exc:
        logger.warning("Не удалось получить статус участника %s: %s", user.id, exc)
        return

    if not await is_bot_admin(update, context):
        logger.warning("Бот не админ в чате %s — пропуск сообщения", chat.id)
        return

    text = message.text or message.caption or ""
    detector: SpamDetector = context.bot_data["detector"]
    verdict = detector.analyze(
        text,
        has_forward=message.forward_origin is not None,
        is_new_member=False,
        username=user.username,
    )

    if not verdict.is_spam:
        return

    logger.info(
        "Спам от user_id=%s (@%s) в chat_id=%s score=%s reasons=%s",
        user.id,
        user.username,
        chat.id,
        verdict.score,
        verdict.reasons,
    )

    try:
        await message.delete()
    except (BadRequest, Forbidden) as exc:
        logger.error("Не удалось удалить сообщение: %s", exc)
        return

    try:
        await context.bot.ban_chat_member(chat.id, user.id)
        action = "заблокирован"
    except Forbidden:
        action = "не заблокирован (нет прав)"
    except BadRequest as exc:
        action = f"не заблокирован ({exc})"

    # Уведомление в чат (можно отключить, закомментировав блок ниже)
    try:
        display = user.full_name or str(user.id)
        reasons = ", ".join(verdict.reasons[:3]) or "подозрительный контент"
        await context.bot.send_message(
            chat_id=cfg.admin_chat_id,
            text=(
                f"🚫 Удалено спам-сообщение от {display}.\n"
                f"Пользователь {action}.\n"
                f"Причина: {reasons}"
            ),
        )
    except TelegramError as exc:
        logger.debug("Не отправлено уведомление в чат: %s", exc)

    _log_incident(context, chat.id, user.id, user.username, verdict.score, verdict.reasons)

async def handle_service_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    cfg = context.bot_data["config"]
    if cfg.allowed_chat_ids and chat.id not in cfg.allowed_chat_ids:
        return

    if not await is_bot_admin(update, context):
        logger.warning("Бот не админ в чате %s — пропуск сервисного сообщения", chat.id)
        return

    # Удаление сообщений о вступлении
    if message.new_chat_members:
        for new_member in message.new_chat_members:
            if not new_member.is_bot:
                try:
                    await message.delete()
                    logger.info(
                        "Удалено сообщение о вступлении пользователя %s (@%s) в чат %s",
                        new_member.id,
                        new_member.username,
                        chat.id,
                    )
                except (BadRequest, Forbidden) as exc:
                    logger.error("Не удалось удалить сообщение о вступлении: %s", exc)

    # Удаление сообщений о выходе
    if message.left_chat_member:
        try:
            await message.delete()
            logger.info(
                "Удалено сообщение о выходе пользователя %s (@%s) из чата %s",
                message.left_chat_member.id,
                message.left_chat_member.username,
                chat.id,
            )
        except (BadRequest, Forbidden) as exc:
            logger.error("Не удалось удалить сообщение о выходе: %s", exc)

def _log_incident(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_id: int,
    username: str | None,
    score: int,
    reasons: list[str],
) -> None:
    incidents: list = context.application.bot_data.setdefault("incidents", [])
    incidents.append(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "chat_id": chat_id,
            "user_id": user_id,
            "username": username,
            "score": score,
            "reasons": reasons,
        }
    )
    # Храним последние 500 записей в памяти
    if len(incidents) > 500:
        del incidents[: len(incidents) - 500]


def main() -> None:
    cfg = load_config()
    setup_logging(cfg.log_level)

    detector = SpamDetector(threshold=cfg.spam_threshold)

    app = (
        Application.builder()
        .token(cfg.token)
        .build()
    )

    app.bot_data["config"] = cfg
    app.bot_data["detector"] = detector

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("chatid", cmd_chatid))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.CAPTION) & (~filters.COMMAND),
            handle_message,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER,
            handle_service_messages,
        )
    )

    logger.info("Бот запущен. Порог спама: %s", cfg.spam_threshold)
    if cfg.allowed_chat_ids:
        logger.info("Whitelist чатов: %s", cfg.allowed_chat_ids)

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
