"""Telegram service — send tender-open notifications with Да/Нет inline buttons.

Security:
  - Bot token is read from settings, never hardcoded or logged.
  - async with telegram.Bot(token): pattern is used so the session is closed
    after each message (no persistent bot connection in the worker process).

Reference: 05-RESEARCH.md lines 494-524 (Pattern 4: PTB send helper).
"""

from __future__ import annotations

import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


async def send_tender_notification(
    bot_token: str,
    chat_id: int,
    number_anno: str,
    application_id: int,
) -> None:
    """Send a Telegram message with Да/Нет inline keyboard when a tender opens.

    Uses `async with telegram.Bot(token):` so the underlying HTTP session is
    properly closed after the message is sent — no singleton bot instance.

    Callback data format:
      "confirm:yes:{application_id}"  →  immediate submit
      "confirm:no:{application_id}"   →  cancel (mark_error)

    Args:
        bot_token: Telegram bot token from settings.telegram_bot_token.
        chat_id: User's Telegram chat ID (User.telegram_chat_id).
        number_anno: Tender number in format "NNNNNNN-N" (e.g. "17163708-1").
        application_id: TenderIt Application.id — embedded in callback_data.
    """
    keyboard = [
        [
            InlineKeyboardButton(
                "Да",
                callback_data=f"confirm:yes:{application_id}",
            ),
            InlineKeyboardButton(
                "Нет",
                callback_data=f"confirm:no:{application_id}",
            ),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    async with telegram.Bot(bot_token) as bot:
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"Тендер №{number_anno} открыт для подачи заявок.\n"
                "Подаём заявку?"
            ),
            reply_markup=reply_markup,
        )
