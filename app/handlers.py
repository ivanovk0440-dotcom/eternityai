"""Обработчики магазина: витрина, карточка товара, оплата, выдача файла.

Название сервиса не встречается ни в одном тексте до оплаты: оно выдаётся отдельным
сообщением (texts.REVEAL) вместе с файлом и позже — по кнопке «🔗 Сервис и ссылка».
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

import keyboards as kb
import texts
from config import config
from db import storage

router = Router()
log = logging.getLogger(__name__)

GUIDE_FILENAME = "Guide_AI_Agent_2026.pdf"


def _is_free(user) -> bool:
    """Свои люди получают гайд бесплатно (список в .env: FREE_USERNAMES)."""
    return config.is_free(user.id, user.username)


def _is_admin(user) -> bool:
    return config.is_admin(user.id, user.username)


# --------------------------------------------------------------------------- utils
async def _swap(target: CallbackQuery, text: str, markup, parse_mode: str = "HTML") -> None:
    """Меняем текущий экран на новый: подпись фото или текст сообщения."""
    msg = target.message
    if msg is None:
        await target.bot.send_message(target.from_user.id, text, reply_markup=markup, parse_mode=parse_mode)
        return
    # подпись к медиа ограничена 1024 символами — длинный экран отправляем новым сообщением
    can_caption = (msg.photo or msg.document or msg.video) and len(text) <= 1000
    try:
        if can_caption:
            await msg.edit_caption(caption=text, reply_markup=markup, parse_mode=parse_mode)
        elif not (msg.photo or msg.document or msg.video):
            await msg.edit_text(text, reply_markup=markup, parse_mode=parse_mode, disable_web_page_preview=True)
        else:
            raise TelegramBadRequest(method=None, message="caption too long → отправляем новым сообщением")
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc):
            return
        await target.bot.send_message(target.from_user.id, text, reply_markup=markup, parse_mode=parse_mode)


async def _send_showcase(message: Message) -> None:
    """Главный экран: обложка + описание + цветные кнопки."""
    has_access = storage.has_access(message.from_user.id) or _is_free(message.from_user)
    photo = FSInputFile(config.cover_path) if config.cover_path.exists() else None
    if photo:
        await message.answer_photo(
            photo=photo,
            caption=texts.HELLO,
            reply_markup=kb.product_card(has_access),
            parse_mode="HTML",
        )
    else:
        await message.answer(texts.HELLO, reply_markup=kb.product_card(has_access), parse_mode="HTML")


async def _reveal(bot, chat_id: int) -> None:
    """Название сервиса и ссылка — только покупателю."""
    await bot.send_message(
        chat_id,
        texts.REVEAL,
        reply_markup=kb.service_kb(),
        parse_mode="HTML",
    )


async def _grant_free(bot, chat_id: int, user) -> None:
    """Бесплатный доступ для своих: доступ в базу + раскрытие + файл."""
    storage.grant_free(user.id, username=user.username, full_name=user.full_name)
    await bot.send_message(chat_id, texts.FREE_ACCESS, parse_mode="HTML")
    await _deliver(bot, chat_id, user.id, reveal=True)


async def _deliver(bot, chat_id: int, user_id: int, reveal: bool = False) -> None:
    """Выдача: сообщение с названием сервиса и ссылкой + файл товара."""
    if reveal:
        await _reveal(bot, chat_id)
    if not config.guide_path.exists():
        log.error("Файл товара не найден: %s", config.guide_path)
        await bot.send_message(
            chat_id,
            "⚠️ Файл временно недоступен. Напишите в поддержку — выдадим вручную.",
            reply_markup=kb.support_kb(),
        )
        return
    await bot.send_document(
        chat_id=chat_id,
        document=FSInputFile(config.guide_path, filename=GUIDE_FILENAME),
        caption=texts.DELIVERY_CAPTION,
        reply_markup=kb.after_purchase(),
        parse_mode="HTML",
    )


# --------------------------------------------------------------------------- команды
@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject) -> None:
    storage.touch_user(message.from_user.id)
    # свой человек: доступ без оплаты выдаётся сразу
    if _is_free(message.from_user) and not storage.has_access(message.from_user.id):
        await _grant_free(message.bot, message.chat.id, message.from_user)
        return
    # deep-link вида /start buy — сразу открываем оформление
    if (command.args or "").strip().lower() in {"buy", "pay"}:
        await message.answer(texts.BUY_SCREEN, reply_markup=kb.checkout(), parse_mode="HTML")
        return
    await _send_showcase(message)


@router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    await _send_showcase(message)


@router.message(Command("buy"))
async def cmd_buy(message: Message) -> None:
    storage.touch_user(message.from_user.id)
    if _is_free(message.from_user) and not storage.has_access(message.from_user.id):
        await _grant_free(message.bot, message.chat.id, message.from_user)
        return
    if storage.has_access(message.from_user.id):
        await message.answer("У вас уже есть этот гайд — файл ниже.", reply_markup=kb.back())
        await _deliver(message.bot, message.chat.id, message.from_user.id)
        return
    await message.answer(texts.BUY_SCREEN, reply_markup=kb.checkout(), parse_mode="HTML")


@router.message(Command("mypurchases", "download"))
async def cmd_mypurchases(message: Message) -> None:
    if _is_free(message.from_user) and not storage.has_access(message.from_user.id):
        await _grant_free(message.bot, message.chat.id, message.from_user)
        return
    if storage.has_access(message.from_user.id):
        await message.answer(
            texts.MY_PURCHASES_OK.format(name=config.product_name),
            reply_markup=kb.after_purchase(),
            parse_mode="HTML",
        )
        await _deliver(message.bot, message.chat.id, message.from_user.id)
    else:
        await message.answer(texts.MY_PURCHASES_EMPTY, reply_markup=kb.main_menu(), parse_mode="HTML")


@router.message(Command("service"))
async def cmd_service(message: Message) -> None:
    """Название сервиса и ссылка — для тех, кто уже купил."""
    if storage.has_access(message.from_user.id) or _is_free(message.from_user):
        await message.answer(texts.REVEAL, reply_markup=kb.service_kb(), parse_mode="HTML")
    else:
        await message.answer(texts.NO_ACCESS_SERVICE, reply_markup=kb.buy_from_info(), parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(texts.HELP, reply_markup=kb.support_kb(), parse_mode="HTML")


@router.message(Command("terms"))
async def cmd_terms(message: Message) -> None:
    await message.answer(texts.TERMS, reply_markup=kb.back(), parse_mode="HTML")


@router.message(Command("paysupport"))
async def cmd_paysupport(message: Message) -> None:
    """Обязательная команда для ботов с Telegram Stars: вопросы по оплате."""
    await message.answer(texts.HELP, reply_markup=kb.support_kb(), parse_mode="HTML")


# --------------------------------------------------------------------------- витрина
@router.callback_query(F.data == "menu")
async def cb_menu(callback: CallbackQuery) -> None:
    has_access = storage.has_access(callback.from_user.id)
    await _swap(callback, texts.HELLO, kb.product_card(has_access))
    await callback.answer()


@router.callback_query(F.data == "inside")
async def cb_inside(callback: CallbackQuery) -> None:
    await _swap(callback, texts.INSIDE, kb.buy_from_info())
    await callback.answer()


@router.callback_query(F.data == "faq")
async def cb_faq(callback: CallbackQuery) -> None:
    await _swap(callback, texts.FAQ, kb.buy_from_info())
    await callback.answer()


@router.callback_query(F.data == "support")
async def cb_support(callback: CallbackQuery) -> None:
    await _swap(callback, texts.HELP, kb.support_kb())
    await callback.answer()


@router.callback_query(F.data == "how")
async def cb_how(callback: CallbackQuery) -> None:
    await _swap(callback, texts.HOW_IT_WORKS, kb.buy_from_info())
    await callback.answer()


@router.callback_query(F.data == "service")
async def cb_service(callback: CallbackQuery) -> None:
    """Повторная выдача названия сервиса и ссылки — только покупателям."""
    if not storage.has_access(callback.from_user.id) and not _is_free(callback.from_user):
        await callback.answer("Ссылка доступна после оплаты", show_alert=True)
        await _swap(callback, texts.NO_ACCESS_SERVICE, kb.buy_from_info())
        return
    await _swap(callback, texts.REVEAL, kb.service_kb())
    await callback.answer()


# --------------------------------------------------------------------------- покупка
@router.callback_query(F.data == "buy")
async def cb_buy(callback: CallbackQuery) -> None:
    if _is_free(callback.from_user) and not storage.has_access(callback.from_user.id):
        await callback.answer("Для вас — бесплатно 🎁")
        await _grant_free(callback.bot, callback.message.chat.id, callback.from_user)
        return
    if storage.has_access(callback.from_user.id):
        await callback.answer("У вас уже есть гайд 🙂", show_alert=True)
        await _deliver(callback.bot, callback.message.chat.id, callback.from_user.id)
        return
    markup = kb.demo_checkout() if config.demo_mode else kb.checkout()
    await _swap(callback, texts.BUY_SCREEN, markup)
    await callback.answer()


@router.callback_query(F.data == "pay")
async def cb_pay(callback: CallbackQuery) -> None:
    """Настоящий счёт в Telegram Stars (currency XTR, provider_token пустой)."""
    if storage.has_access(callback.from_user.id):
        await callback.answer("Гайд уже оплачен 🙂", show_alert=True)
        return
    try:
        await callback.bot.send_invoice(
            chat_id=callback.from_user.id,
            title=config.product_name,
            description="PDF, 34 страницы: 10 задач с готовыми промптами, интеграции, чек-листы. Название сервиса и ссылка — сразу после оплаты.",
            payload=f"guide:{callback.from_user.id}",
            provider_token="",             # для Stars токен провайдера не нужен
            currency="XTR",
            prices=[LabeledPrice(label="Гайд по AI-агенту", amount=config.price_stars)],
            start_parameter="guide",
            protect_content=True,
        )
        await callback.answer()
    except TelegramBadRequest as exc:
        log.exception("Не удалось выставить счёт: %s", exc)
        await callback.answer("Не удалось создать счёт. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "demo_pay")
async def cb_demo_pay(callback: CallbackQuery) -> None:
    """Демонстрационная выдача без списания звёзд — только если DEMO_MODE=true."""
    if not config.demo_mode:
        await callback.answer("Демо-режим выключен.", show_alert=True)
        return
    storage.add_order(
        user_id=callback.from_user.id,
        stars=0,
        status="demo",
        username=callback.from_user.username,
        full_name=callback.from_user.full_name,
    )
    await _swap(callback, texts.DEMO_OK, kb.after_purchase())
    await callback.answer("Демо-оплата прошла ✅")
    await _deliver(callback.bot, callback.message.chat.id, callback.from_user.id, reveal=True)


@router.callback_query(F.data == "download")
async def cb_download(callback: CallbackQuery) -> None:
    if not storage.has_access(callback.from_user.id) and not _is_free(callback.from_user):
        await callback.answer("Сначала оформите покупку 🙂", show_alert=True)
        await _swap(callback, texts.BUY_SCREEN, kb.checkout())
        return
    await callback.answer("Отправляем файл…")
    await _deliver(callback.bot, callback.message.chat.id, callback.from_user.id, reveal=False)


@router.callback_query(F.data == "mypurchases")
async def cb_mypurchases(callback: CallbackQuery) -> None:
    if _is_free(callback.from_user) and not storage.has_access(callback.from_user.id):
        await _grant_free(callback.bot, callback.message.chat.id, callback.from_user)
        await callback.answer()
        return
    if storage.has_access(callback.from_user.id):
        await _swap(
            callback,
            texts.MY_PURCHASES_OK.format(name=config.product_name),
            kb.after_purchase(),
        )
        await _deliver(callback.bot, callback.message.chat.id, callback.from_user.id)
    else:
        await _swap(callback, texts.MY_PURCHASES_EMPTY, kb.main_menu())
    await callback.answer()


@router.callback_query(F.data == "reviews")
async def cb_reviews(callback: CallbackQuery) -> None:
    text = (
        "<b>⭐ Отзывы покупателей</b>\n\n"
        "«Собрал лендинг за один вечер, раньше отдавал подрядчику за 40 тысяч».\n"
        "«Наконец понял, как формулировать задачу, чтобы не переделывать по пять раз».\n"
        "«Раздел про коннекторы один стоит цены гайда».\n\n"
        "<i>Свежие отзывы — по кнопке ниже.</i>"
    )
    await _swap(callback, text, kb.review_kb())
    await callback.answer()


# --------------------------------------------------------------------------- оплата
@router.pre_checkout_query()
async def on_pre_checkout(query: PreCheckoutQuery) -> None:
    """Проверка перед списанием: сумма, валюта, назначение."""
    ok = (
        query.invoice_payload.startswith("guide:")
        and query.currency == "XTR"
        and query.total_amount == config.price_stars
    )
    if ok:
        await query.answer(ok=True)
    else:
        log.warning("Отклонён платёж: %s", query.invoice_payload)
        await query.answer(ok=False, error_message="Счёт устарел. Откройте магазин и попробуйте снова.")


@router.message(F.successful_payment)
async def on_paid(message: Message) -> None:
    payment = message.successful_payment
    storage.add_order(
        user_id=message.from_user.id,
        stars=payment.total_amount,
        status="paid",
        telegram_charge=payment.telegram_payment_charge_id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )
    log.info("Оплата: user=%s stars=%s charge=%s", message.from_user.id, payment.total_amount,
             payment.telegram_payment_charge_id)

    await message.answer(texts.PAYMENT_OK, reply_markup=kb.after_purchase(), parse_mode="HTML")
    await _deliver(message.bot, message.chat.id, message.from_user.id, reveal=True)

    for admin_id in config.admin_ids:
        try:
            await message.bot.send_message(
                admin_id,
                f"💰 Новая продажа\nuser_id: <code>{message.from_user.id}</code>\n"
                f"сумма: {payment.total_amount} ⭐",
                parse_mode="HTML",
            )
        except Exception:  # админ мог не начинать диалог с ботом
            pass


# --------------------------------------------------------------------------- админ
@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if not _is_admin(message.from_user):
        return
    s = storage.stats()
    await message.answer(texts.ADMIN_STATS.format(**s), parse_mode="HTML")


@router.message(Command("grant"))
async def cmd_grant(message: Message, command: CommandObject) -> None:
    """Выдать доступ вручную: /grant 123456789 — например, после возврата или подарка."""
    if not _is_admin(message.from_user):
        return
    arg = (command.args or "").strip()
    if not arg.isdigit():
        await message.answer("Использование: <code>/grant USER_ID</code>", parse_mode="HTML")
        return
    storage.grant(int(arg))
    await message.answer(f"✅ Доступ выдан пользователю <code>{arg}</code>", parse_mode="HTML")
    try:
        await message.bot.send_message(
            int(arg),
            "🎁 Вам открыт доступ к гайду — файл ниже.",
            reply_markup=kb.after_purchase(),
        )
        await _deliver(message.bot, int(arg), int(arg), reveal=True)
    except Exception:
        await message.answer("Доступ записан, но написать пользователю не удалось (не начинал диалог).")


@router.message(Command("refund"))
async def cmd_refund(message: Message, command: CommandObject) -> None:
    """Возврат звёзд по последнему платежу: /refund USER_ID (требование Telegram Stars)."""
    if not _is_admin(message.from_user):
        return
    arg = (command.args or "").strip()
    if not arg.isdigit():
        await message.answer("Использование: <code>/refund USER_ID</code>", parse_mode="HTML")
        return
    charge = storage.last_paid_charge(int(arg))
    if not charge:
        await message.answer("У пользователя нет оплаченного заказа.")
        return
    try:
        await message.bot.refund_star_payment(user_id=int(arg), telegram_payment_charge_id=charge)
        await message.answer(f"↩️ Возврат выполнен пользователю <code>{arg}</code>", parse_mode="HTML")
    except Exception as exc:
        await message.answer(f"Не удалось вернуть: {exc}")
