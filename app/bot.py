#!/usr/bin/env python3
"""
Arena Store — Telegram-магазин одного цифрового товара.

Запуск:
    pip install -r requirements.txt
    cp .env.example .env      # вставьте BOT_TOKEN
    python bot.py

Проверка конфигурации без сети:
    python bot.py --check
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, ErrorEvent

from config import BASE_DIR, config
from handlers import router
from db import storage

log = logging.getLogger("arena-store")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands([
        BotCommand(command="start", description="🛒 Витрина магазина"),
        BotCommand(command="buy", description="💳 Купить гайд"),
        BotCommand(command="mypurchases", description="📥 Скачать купленное"),
        BotCommand(command="service", description="🔗 Сервис и ссылка"),
        BotCommand(command="help", description="🆘 Поддержка"),
        BotCommand(command="paysupport", description="❓ Вопросы по оплате"),
        BotCommand(command="terms", description="📄 Условия"),
    ])


async def on_error(event: ErrorEvent) -> None:
    log.exception("Ошибка при обработке апдейта: %s", event.exception, exc_info=event.exception)


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(router)
    dp.errors.register(on_error)
    return dp


async def main() -> None:
    setup_logging()
    problems = config.validate()
    if problems:
        for p in problems:
            log.error("Конфигурация: %s", p)
        log.error("Запуск остановлен. Смотрите .env.example и README.md")
        sys.exit(1)

    bot = Bot(
        token=config.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )
    dp = build_dispatcher()

    try:
        me = await bot.get_me()
    except TelegramUnauthorizedError:
        log.error("Telegram отклонил токен. Проверьте BOT_TOKEN в .env (токен выдаёт @BotFather).")
        await bot.session.close()
        sys.exit(1)
    log.info("Бот @%s запущен · цена %s ⭐ · демо-режим: %s", me.username, config.price_stars, config.demo_mode)

    await set_commands(bot)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        storage.close()


def check() -> None:
    """`python bot.py --check` — проверка конфигурации и файлов без подключения к Telegram."""
    setup_logging()
    problems = config.validate()
    print("— Конфигурация —")
    print(f"  товар:        {config.product_name}")
    print(f"  цена:         {config.price_stars} ⭐ (было {config.old_price_stars})")
    print(f"  файл товара:  {config.guide_path} ({'ok' if config.guide_path.exists() else 'НЕТ'})")
    print(f"  демо-режим:   {config.demo_mode}")
    print(f"  база:         {config.db_path}")
    print(f"  обложка:      {config.cover_path} ({'ok' if config.cover_path.exists() else 'НЕТ'})")
    print(f"  сервис:       скрыт до оплаты → {config.service_name} · {config.service_agent_url}")
    print(f"  админы:       {config.admin_ids or '—'}")
    dotenv = config.dotenv_path
    print(f"  файл .env:    {dotenv if dotenv else 'нет (только переменные окружения)'}")
    if problems:
        print("\n❌ Проблемы:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("\n✅ Конфигурация корректна. Можно запускать: python bot.py")


if __name__ == "__main__":
    if "--check" in sys.argv:
        check()
    else:
        try:
            asyncio.run(main())
        except (KeyboardInterrupt, SystemExit):
            print("\nОстановлено пользователем.")
