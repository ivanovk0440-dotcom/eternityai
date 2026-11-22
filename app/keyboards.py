"""
Клавиатуры магазина.
Цвет кнопки задаётся полем style (Bot API 9.0+): primary — синий, success — зелёный, danger — красный.
На клиентах старше февраля 2026 кнопки просто останутся без цвета — логика не ломается.
"""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton as B
from aiogram.types import InlineKeyboardMarkup as M

from config import config

PRIMARY, SUCCESS, DANGER = "primary", "success", "danger"


def _url_kb(rows: list[list[B]]) -> M:
    return M(inline_keyboard=[r for r in rows if r])


def main_menu(has_access: bool = False) -> M:
    """Витрина: зелёная кнопка покупки, синие информационные, красная — закрыть."""
    rows: list[list[B]] = [
        [B(text=f"🛒 Купить за {config.price_stars} ⭐", callback_data="buy", style=SUCCESS)],
        [
            B(text="📖 Что внутри", callback_data="inside", style=PRIMARY),
            B(text="🧾 Как это работает", callback_data="how", style=PRIMARY),
        ],
        [
            B(text="❓ Вопросы", callback_data="faq", style=PRIMARY),
            # красный акцент — только для «выхода» или поддержки
            B(text="🆘 Поддержка", callback_data="support", style=DANGER),
        ],
    ]
    if has_access:
        rows.append([B(text="📥 Скачать гайд", callback_data="download", style=SUCCESS)])
    else:
        rows.append([B(text="📥 Мои покупки", callback_data="mypurchases", style=PRIMARY)])
    return _url_kb(rows)


def product_card(has_access: bool = False) -> M:
    """Клавиатура под карточкой товара (под фото обложки) — та же витрина, без «лишнего» меню."""
    rows: list[list[B]] = []
    if has_access:
        rows.append([B(text="📥 Скачать гайд", callback_data="download", style=SUCCESS)])
    else:
        rows.append([B(text=f"🛒 Купить за {config.price_stars} ⭐", callback_data="buy", style=SUCCESS)])
    rows.append([
        B(text="📖 Что внутри", callback_data="inside", style=PRIMARY),
        B(text="🧾 Как это работает", callback_data="how", style=PRIMARY),
    ])
    rows.append([
        B(text="❓ Вопросы", callback_data="faq", style=PRIMARY),
        B(text="🆘 Поддержка", callback_data="support", style=DANGER),
    ])
    return _url_kb(rows)


def checkout() -> M:
    return _url_kb([
        [B(text=f"💳 Оплатить {config.price_stars} ⭐", callback_data="pay", style=SUCCESS)],
        [B(text="✖️ Отмена", callback_data="menu", style=DANGER)],
    ])


def demo_checkout() -> M:
    """Кнопки для режима DEMO_MODE: имитация оплаты + возврат."""
    return _url_kb([
        [B(text="🧪 Сымитировать оплату", callback_data="demo_pay", style=SUCCESS)],
        [B(text="✖️ Отмена", callback_data="menu", style=DANGER)],
    ])


def after_purchase() -> M:
    rows: list[list[B]] = [
        [B(text="📥 Скачать снова", callback_data="download", style=SUCCESS)],
        [B(text="🔗 Сервис и ссылка", callback_data="service", style=PRIMARY)],
        [
            B(text="⭐ Отзывы", url=config.reviews_url, style=PRIMARY) if config.reviews_url else None,
            B(text="📚 В магазин", callback_data="menu", style=PRIMARY),
        ],
        [B(text="🆘 Поддержка", callback_data="support", style=DANGER)],
    ]
    return _url_kb([[b for b in r if b] for r in rows])


def back(callback: str = "menu", label: str = "⬅️ В меню") -> M:
    return _url_kb([[B(text=label, callback_data=callback, style=PRIMARY)]])


def buy_from_info() -> M:
    return _url_kb([
        [B(text=f"🛒 Купить за {config.price_stars} ⭐", callback_data="buy", style=SUCCESS)],
        [B(text="⬅️ Назад", callback_data="menu", style=PRIMARY)],
    ])


def service_kb() -> M:
    return _url_kb([
        [B(text="📥 Скачать гайд", callback_data="download", style=SUCCESS)],
        [B(text="⬅️ В магазин", callback_data="menu", style=PRIMARY)],
    ])


def support_kb() -> M:
    rows: list[list[B]] = []
    if config.support_url:
        rows.append([B(text="✍️ Написать в поддержку", url=config.support_url, style=SUCCESS)])
    else:
        rows.append([B(text=f"🛒 Купить за {config.price_stars} ⭐", callback_data="buy", style=SUCCESS)])
    rows.append([B(text="⬅️ В меню", callback_data="menu", style=PRIMARY)])
    return _url_kb(rows)


def review_kb() -> M:
    rows: list[list[B]] = []
    if config.reviews_url:
        rows.append([B(text="⭐ Открыть отзывы", url=config.reviews_url, style=PRIMARY)])
    rows.append([B(text=f"🛒 Купить за {config.price_stars} ⭐", callback_data="buy", style=SUCCESS)])
    rows.append([B(text="⬅️ В меню", callback_data="menu", style=PRIMARY)])
    return _url_kb(rows)
