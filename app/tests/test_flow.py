#!/usr/bin/env python3
"""
Интеграционный тест магазина без сети и без токена.
Подменяет транспорт aiogram на фейковую сессию и прогоняет полный путь покупателя:
/start → «Что внутри» → «Купить» → демо-оплата → раскрытие сервиса + выдача файла →
повторное скачивание, а также реальную ветку Telegram Stars (pre_checkout_query → successful_payment).
Отдельно проверяется главное условие: до оплаты название сервиса не появляется ни в одном сообщении.

Запуск:  python tests/test_flow.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# отдельная тестовая база и гарантированно включённый демо-режим
_tmpdir = tempfile.mkdtemp(prefix="arena-shop-test-")
os.environ["DB_FILE"] = os.path.join(_tmpdir, "test.db")
os.environ["DEMO_MODE"] = "true"
os.environ["BOT_TOKEN"] = "42:TEST"
os.environ["ADMIN_IDS"] = "999"

from aiogram import Bot                      # noqa: E402
from aiogram.client.session.base import BaseSession  # noqa: E402
from aiogram.methods import (               # noqa: E402
    AnswerPreCheckoutQuery, EditMessageCaption, EditMessageText, GetMe, SendDocument,
    SendInvoice, SendMessage, SendPhoto,
)
from aiogram.methods.base import TelegramMethod  # noqa: E402
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, PreCheckoutQuery, Update  # noqa: E402
from aiogram.types import Chat, PhotoSize, SuccessfulPayment, User  # noqa: E402

import keyboards as kb                       # noqa: E402
import texts                                 # noqa: E402
from bot import build_dispatcher             # noqa: E402
from config import config                    # noqa: E402
from db import storage                       # noqa: E402

USER_ID = 100500
FORBIDDEN = ("arena", "арена", "agent mode")   # до оплаты этих слов быть не должно
CHAT_ID = 100500
BOT_ID = 42

ok_count = 0
failures: list[str] = []


def check(condition: bool, title: str) -> None:
    global ok_count
    if condition:
        ok_count += 1
        print(f"  ✅ {title}")
    else:
        failures.append(title)
        print(f"  ❌ {title}")


class FakeSession(BaseSession):
    """Записывает вызовы Bot API и возвращает правдоподобные ответы."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[TelegramMethod] = []

    async def make_request(self, bot, method, timeout=None):  # type: ignore[override]
        self.calls.append(method)
        if isinstance(method, GetMe):
            return User(id=BOT_ID, is_bot=True, first_name="Arena Store", username="arena_store_bot")
        chat_id = getattr(method, "chat_id", CHAT_ID)
        return Message(
            message_id=len(self.calls),
            date=datetime.now(timezone.utc),
            chat=Chat(id=chat_id, type="private"),
            text=getattr(method, "text", None),
        )

    async def stream_content(self, *args, **kwargs):  # type: ignore[override]
        if False:  # pragma: no cover
            yield b""

    async def close(self) -> None:  # type: ignore[override]
        return None

    # ---- помощники для проверок ----
    def of(self, cls) -> list:
        return [c for c in self.calls if isinstance(c, cls)]


def make_message(text: str | None = None, payment: SuccessfulPayment | None = None) -> Message:
    return Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=Chat(id=CHAT_ID, type="private"),
        from_user=User(id=USER_ID, is_bot=False, first_name="Тест", username="tester"),
        text=text,
        successful_payment=payment,
    )


def make_callback(data: str, user_id: int = USER_ID, username: str = "tester") -> CallbackQuery:
    return CallbackQuery(
        id="cb1",
        from_user=User(id=user_id, is_bot=False, first_name="Тест", username=username),
        chat_instance="ci",
        data=data,
        message=make_message("предыдущий экран"),
    )


def make_free_message(username: str = "asnaebp", user_id: int = 424242) -> Message:
    """Сообщение от «своего» пользователя — он получает гайд бесплатно."""
    return Message(
        message_id=2,
        date=datetime.now(timezone.utc),
        chat=Chat(id=CHAT_ID, type="private"),
        from_user=User(id=user_id, is_bot=False, first_name="Свой", username=username),
        text="/start",
    )


async def main() -> None:
    session = FakeSession()
    bot = Bot(token=config.token, session=session)
    dp = build_dispatcher()

    print("\n— Клавиатуры и стили —")
    valid_styles = {"primary", "success", "danger"}
    for name, markup in {
        "main_menu": kb.main_menu(),
        "product_card": kb.product_card(),
        "checkout": kb.checkout(),
        "demo_checkout": kb.demo_checkout(),
        "after_purchase": kb.after_purchase(),
        "support": kb.support_kb(),
        "review": kb.review_kb(),
    }.items():
        assert isinstance(markup, InlineKeyboardMarkup)
        styles = {b.style for row in markup.inline_keyboard for b in row}
        check(styles <= valid_styles, f"{name}: цвета только primary/success/danger {sorted(s for s in styles if s)}")
        check(any(b.style == "success" for row in markup.inline_keyboard for b in row),
              f"{name}: есть зелёная кнопка действия")
    check(len(texts.HELLO) < 1024, "приветствие укладывается в лимит подписи к фото (1024)")
    check(len(texts.DELIVERY_CAPTION) < 1024, "подпись к файлу укладывается в лимит")

    print("\n— Ключевые обещания —")
    check("codex" in texts.HELLO.lower() and "claude code" in texts.HELLO.lower(),
          "витрина упоминает Codex и Claude Code")
    check("бесплатн" in texts.HELLO.lower(), "витрина говорит о бесплатности сервиса")
    check("исследован" in texts.HELLO.lower() and "презентац" in texts.HELLO.lower()
          and "генерац" in texts.HELLO.lower(),
          "витрина перечисляет исследования, презентации и генерацию")
    check("агент" in texts.HELLO.lower(), "главная мысль витрины — агент")
    check("codex" in texts.FAQ.lower(), "FAQ отвечает на вопрос про Codex")
    check("бесплатн" in texts.REVEAL.lower(), "раскрытие повторяет тему бесплатности")

    print("\n— Секрет до оплаты —")
    for name in dir(texts):
        if name.isupper() and isinstance(getattr(texts, name), str) and name != "REVEAL":
            value = getattr(texts, name).lower()
            check(not any(w in value for w in FORBIDDEN), f"texts.{name}: название сервиса не упоминается")
    for name, markup in {"main_menu": kb.main_menu(), "product_card": kb.product_card(),
                         "checkout": kb.checkout(), "demo_checkout": kb.demo_checkout(),
                         "buy_from_info": kb.buy_from_info(), "support": kb.support_kb()}.items():
        labels = " ".join(b.text for row in markup.inline_keyboard for b in row).lower()
        check(not any(w in labels for w in FORBIDDEN), f"{name}: в кнопках нет названия сервиса")

    print("\n— Файлы товара —")
    check(config.guide_path.exists(), f"файл гайда на месте: {config.guide_path.name}")
    check(config.guide_path.stat().st_size > 500_000, "PDF не пустой")
    check("arena" not in config.guide_path.name.lower(), "имя файла товара не выдаёт сервис")
    check(config.cover_path.exists(), "обложка карточки товара на месте")

    print("\n— Путь покупателя —")
    await dp.feed_update(bot, Update(update_id=1, message=make_message("/start")))
    photos = session.of(SendPhoto)
    check(len(photos) == 1, "/start отправляет карточку товара с обложкой")
    markup = photos[0].reply_markup
    flat = [b for row in markup.inline_keyboard for b in row]
    check(any(b.style == "success" and "Купить" in b.text for b in flat), "главная кнопка «Купить» — зелёная")
    check(any(b.style == "primary" for b in flat) and any(b.style == "danger" for b in flat),
          "на витрине есть синие и красная кнопки")

    session.calls.clear()
    await dp.feed_update(bot, Update(update_id=2, callback_query=make_callback("inside")))
    check(bool(session.of(EditMessageText)), "«Что внутри» редактирует текущий экран")

    # пользователь нажал кнопку под фото-карточкой, а экран «Что внутри» длиннее лимита подписи
    photo_msg = Message(
        message_id=3, date=datetime.now(timezone.utc), chat=Chat(id=CHAT_ID, type="private"),
        from_user=User(id=USER_ID, is_bot=False, first_name="Тест"),
        photo=[PhotoSize(file_id="f", file_unique_id="u", width=800, height=1131)],
    )
    photo_cb = make_callback("inside").model_copy(update={"message": photo_msg})
    session.calls.clear()
    await dp.feed_update(bot, Update(update_id=21, callback_query=photo_cb))
    check(bool(session.of(SendMessage)) and not session.of(EditMessageCaption),
          "длинный экран под фото уходит новым сообщением (лимит подписи 1024)")

    session.calls.clear()
    await dp.feed_update(bot, Update(update_id=3, callback_query=make_callback("buy")))
    edit = session.of(EditMessageText)
    check(bool(edit), "«Купить» открывает экран оформления")
    pay_buttons = [b for row in edit[0].reply_markup.inline_keyboard for b in row]
    check(any(b.callback_data == "demo_pay" for b in pay_buttons), "в демо-режиме доступна имитация оплаты")

    session.calls.clear()
    await dp.feed_update(bot, Update(update_id=4, callback_query=make_callback("demo_pay")))
    docs = session.of(SendDocument)
    check(len(docs) == 1, "после оплаты файл отправлен")
    sent = " ".join((m.text or "") for m in session.of(SendMessage)).lower()
    check("arena" in sent and "arena.ai/agent" in sent, "после оплаты выданы название сервиса и ссылка")
    caption = (docs[0].caption or "").lower() if docs else ""
    check("arena" not in caption, "подпись к файлу не раскрывает сервис — он в отдельном сообщении")
    order = session.calls.index(docs[0]) if docs else 0
    reveal_pos = next((i for i, m in enumerate(session.calls)
                       if isinstance(m, SendMessage) and "arena" in (m.text or "").lower()), -1)
    check(reveal_pos != -1 and reveal_pos < order, "сначала сообщение с сервисом, затем файл")
    check(docs and docs[0].document is not None, "документ передан как файл, а не ссылка")
    check(storage.has_access(USER_ID), "заказ сохранён в базе")

    session.calls.clear()
    await dp.feed_update(bot, Update(update_id=5, callback_query=make_callback("download")))
    check(len(session.of(SendDocument)) == 1, "повторное скачивание работает")

    session.calls.clear()
    await dp.feed_update(bot, Update(update_id=6, message=make_message("/start")))
    markup = session.of(SendPhoto)[0].reply_markup
    texts_all = [b.text for row in markup.inline_keyboard for b in row]
    check(any("Скачать гайд" in t for t in texts_all), "после покупки витрина знает о доступе")

    session.calls.clear()
    await dp.feed_update(bot, Update(update_id=22, callback_query=make_callback("service", 777001)))
    edit = session.of(EditMessageText)
    check(edit and "покупателям" in (edit[0].text or "").lower(), "ссылка на сервис скрыта от неоплативших")

    print("\n— Бесплатный доступ для своих —")
    check(config.is_free(424242, "asnaebp"), "asnaebp в списке бесплатного доступа")
    check(config.is_free(424243, "vladmyaz"), "vladmyaz в списке бесплатного доступа")
    check(not config.is_free(999999, "stranger"), "посторонний пользователь не проходит")
    check(config.is_admin(424242, "asnaebp"), "свой пользователь — админ (по нику)")

    session.calls.clear()
    await dp.feed_update(bot, Update(update_id=31, message=make_free_message()))
    free_docs = session.of(SendDocument)
    check(len(free_docs) == 1, "свой пользователь получает файл без оплаты")
    free_text = " ".join((m.text or "") for m in session.of(SendMessage)).lower()
    check("arena" in free_text and "arena.ai/agent" in free_text,
          "свой пользователь получает название сервиса и ссылку")
    check(storage.has_access(424242), "бесплатный доступ записан в базу")
    free_order = storage.recent(1)[0]
    check(free_order["status"] == "free", "в базе статус free")

    print("\n— Ветка Telegram Stars —")
    USER2 = 200200
    session.calls.clear()
    await dp.feed_update(bot, Update(update_id=7, callback_query=make_callback("pay", USER2)))
    invoices = session.of(SendInvoice)
    check(len(invoices) == 1, "выставляется счёт")
    if invoices:
        inv = invoices[0]
        check(inv.currency == "XTR" and inv.provider_token == "", "валюта XTR, токен провайдера пустой")
        check(len(inv.title) <= 32, f"заголовок счёта укладывается в 32 символа: {inv.title!r}")
        check(not any(w in (inv.title + inv.description).lower() for w in FORBIDDEN),
              "в счёте нет названия сервиса")
        check(inv.prices[0].amount == config.price_stars, "сумма счёта совпадает с ценой")
        check(inv.payload == f"guide:{USER2}", "payload привязан к покупателю")

    pre = PreCheckoutQuery(
        id="pcq1",
        from_user=User(id=USER2, is_bot=False, first_name="Тест"),
        currency="XTR",
        total_amount=config.price_stars,
        invoice_payload=f"guide:{USER2}",
    )
    session.calls.clear()
    await dp.feed_update(bot, Update(update_id=8, pre_checkout_query=pre))
    answers = session.of(AnswerPreCheckoutQuery)
    check(answers and answers[0].ok is True, "корректный платёж подтверждён")

    bad = pre.model_copy(update={"total_amount": 1})
    session.calls.clear()
    await dp.feed_update(bot, Update(update_id=9, pre_checkout_query=bad))
    answers = session.of(AnswerPreCheckoutQuery)
    check(answers and answers[0].ok is False, "платёж с неверной суммой отклонён")

    # новая база «чистого» пользователя для проверки реальной оплаты
    OTHER = 555555
    storage._conn.execute("DELETE FROM orders WHERE user_id=?", (OTHER,))
    storage._conn.commit()
    payment = SuccessfulPayment(
        currency="XTR",
        total_amount=config.price_stars,
        invoice_payload=f"guide:{OTHER}",
        telegram_payment_charge_id="charge-123",
        provider_payment_charge_id="provider-123",
    )
    msg = Message(
        message_id=2, date=datetime.now(timezone.utc), chat=Chat(id=OTHER, type="private"),
        from_user=User(id=OTHER, is_bot=False, first_name="Плательщик"), successful_payment=payment,
    )
    session.calls.clear()
    await dp.feed_update(bot, Update(update_id=10, message=msg))
    check(storage.has_access(OTHER), "успешная оплата выдаёт доступ")
    check(len(session.of(SendDocument)) == 1, "после оплаты звёздами файл отправлен")
    check(storage.last_paid_charge(OTHER) == "charge-123", "charge_id сохранён для возврата")

    stats = storage.stats()
    check(stats["paid_orders"] >= 1 and stats["demo_orders"] >= 1, f"статистика считается: {stats}")

    print("\n— Тексты —")
    for name in ("HELLO", "INSIDE", "FAQ", "HELP", "TERMS", "BUY_SCREEN", "PAYMENT_OK", "HOW_IT_WORKS",
                 "FREE_ACCESS"):
        check(len(getattr(texts, name)) > 40, f"{name} заполнен")

    print(f"\n{'=' * 52}\nИтог: {ok_count} проверок пройдено, {len(failures)} провалено")
    if failures:
        for f in failures:
            print("  ❌", f)
        sys.exit(1)
    print("Полный сценарий покупки работает ✅")
    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
