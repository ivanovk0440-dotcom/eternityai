"""
Конфигурация магазина.
Все значения читаются из переменных окружения или из файла .env рядом с ботом.
Секреты в код не попадают.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    """Минимальный загрузчик .env: KEY=VALUE, поддержка кавычек и комментариев."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _find_dotenv() -> Path | None:
    """Ищем .env в разных местах — чтобы работало и в репозитории, и на сервере.

    Порядок: рядом с кодом (app/) → на уровень выше (корень репозитория) → текущий каталог.
    Первый найденный и есть основной; переменные окружения имеют приоритет над файлом.
    """
    candidates = [
        BASE_DIR / ".env",
        BASE_DIR.parent / ".env",
        Path.cwd() / ".env",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


_DOTENV = _find_dotenv()
if _DOTENV is not None:
    _load_dotenv(_DOTENV)


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on", "да"}


def _asset(env_name: str, default: str) -> Path:
    """Путь из переменной окружения: относительный — от папки с кодом, абсолютный — как есть."""
    raw = os.getenv(env_name, default).strip()
    path = Path(raw)
    return path if path.is_absolute() else BASE_DIR / path


def _norm(username: str | None) -> str:
    return (username or "").strip().lstrip("@").lower()


def _names(name: str, default: str = "") -> tuple[str, ...]:
    raw = os.getenv(name, default)
    return tuple(_norm(x) for x in raw.replace(" ", "").split(",") if _norm(x))


def _int(name: str, default: int = 0) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    token: str = os.getenv("BOT_TOKEN", "").strip()

    # --- товар (название сервиса до оплаты нигде не выводится) ---
    product_name: str = os.getenv("PRODUCT_NAME", "Гайд по AI-агенту")
    price_stars: int = _int("PRICE_STARS", 219)
    old_price_stars: int = _int("OLD_PRICE_STARS", 399)

    # --- то, что открывается покупателю после оплаты ---
    service_name: str = os.getenv("SERVICE_NAME", "Arena.ai")
    service_url: str = os.getenv("SERVICE_URL", "https://arena.ai")
    service_agent_url: str = os.getenv("SERVICE_AGENT_URL", "https://arena.ai/agent")

    # --- файлы ---
    # Пути относительные считаются от папки с кодом (app/), абсолютные — как есть.
    guide_path: Path = field(default_factory=lambda: _asset("GUIDE_FILE", "assets/guide.pdf"))
    cover_path: Path = field(default_factory=lambda: _asset("COVER_FILE", "assets/cover.jpg"))

    # --- ссылки ---
    reviews_url: str = os.getenv("REVIEWS_URL", "").strip()
    support_url: str = os.getenv("SUPPORT_URL", "").strip()
    channel_url: str = os.getenv("CHANNEL_URL", "").strip()

    # --- режимы ---
    demo_mode: bool = _bool("DEMO_MODE", True)      # кнопка «демо-оплата» без списания звёзд
    db_path: Path = field(default_factory=lambda: _asset("DB_FILE", "data/shop.db"))

    admin_ids: tuple[int, ...] = field(
        default_factory=lambda: tuple(
            int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.isdigit()
        )
    )
    # доступ без оплаты — по нику или по числовому id
    free_user_ids: tuple[int, ...] = field(
        default_factory=lambda: tuple(
            int(x) for x in os.getenv("FREE_USER_IDS", "").replace(" ", "").split(",") if x.isdigit()
        )
    )
    free_usernames: tuple[str, ...] = field(
        default_factory=lambda: _names("FREE_USERNAMES", "asnaebp,vladmyaz")
    )
    # админы тоже могут заходить по нику
    admin_usernames: tuple[str, ...] = field(
        default_factory=lambda: _names("ADMIN_USERNAMES", "asnaebp,vladmyaz")
    )

    # ------------------------------------------------------------------ проверки
    def is_free(self, user_id: int, username: str | None = None) -> bool:
        """Доступ без оплаты (для своих людей)."""
        if user_id in self.free_user_ids:
            return True
        return _norm(username) in self.free_usernames

    def is_admin(self, user_id: int, username: str | None = None) -> bool:
        if user_id in self.admin_ids:
            return True
        return _norm(username) in self.admin_usernames

    @property
    def dotenv_path(self) -> Path | None:
        """Путь к файлу с настройками (для диагностики)."""
        return _DOTENV

    @property
    def price_label(self) -> str:
        return f"{self.price_stars} ⭐"

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.token or ":" not in self.token:
            problems.append("BOT_TOKEN не задан или имеет неверный формат (см. .env.example)")
        if not self.guide_path.exists():
            problems.append(f"не найден файл товара: {self.guide_path}")
        if self.price_stars <= 0:
            problems.append("PRICE_STARS должен быть больше нуля")
        return problems


config = Config()
