#!/usr/bin/env bash
# Установка магазина на сервере. Токен и настройки — из переменных окружения.
#
#   export BOT_TOKEN=123456:AA...
#   ./install.sh docker      # или: ./install.sh systemd
#
# Если переменных нет, Compose сам прочитает .env из текущей папки.

set -euo pipefail

cd "$(dirname "$0")"
MODE="${1:-docker}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
APP_DIR="${APP_DIR:-/opt/arena-store}"
SERVICE_NAME="arena-store"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
fail() { printf '  \033[31m✗\033[0m %s\n' "$*"; exit 1; }

bold "════════ Установка Telegram-магазина ════════"

# ---------------------------------------------------------------- токен
# 1) из окружения, 2) из .env в текущей папке — иначе ошибка с подсказкой.
if [ -z "${BOT_TOKEN:-}" ] && [ -f .env ]; then
  BOT_TOKEN=$(grep '^BOT_TOKEN=' .env | tail -1 | cut -d= -f2- | tr -d '"' | tr -d "'" | tr -d ' ')
  [ -n "$BOT_TOKEN" ] && export BOT_TOKEN
fi
[ -n "${BOT_TOKEN:-}" ] || fail "Нет BOT_TOKEN. Выполните: export BOT_TOKEN=123456:AA...  (или положите .env рядом)"
ok "токен получен из окружения"

# ---------------------------------------------------------------- проверки
command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "Не найден $PYTHON_BIN. Установите Python 3.11+."

if [ "$MODE" = "docker" ]; then
  command -v docker >/dev/null 2>&1 || fail "Не найден docker. Либо поставьте его, либо запустите: ./install.sh systemd"
  docker compose version >/dev/null 2>&1 || fail "Нужен Docker Compose v2 (docker compose)."
fi

[ -f app/assets/guide.pdf ] || fail "Нет файла app/assets/guide.pdf — положите PDF-гайд в app/assets/."

mkdir -p data && chmod 700 data

# ---------------------------------------------------------------- запуск
if [ "$MODE" = "docker" ]; then
  bold "▸ Docker"
  docker compose build
  docker compose up -d
  ok "Контейнер arena-store запущен"
  echo
  echo "  логи:    docker compose logs -f"
  echo "  рестарт: docker compose restart"
  echo "  проверка: docker compose exec shop python bot.py --check"

elif [ "$MODE" = "systemd" ]; then
  bold "▸ Systemd (без Docker)"
  id -u arena >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin arena
  mkdir -p "$APP_DIR"

  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete --exclude 'data' --exclude '.env' --exclude '__pycache__' app/ "$APP_DIR"/
  else
    find "$APP_DIR" -maxdepth 1 -name '*.py' -delete
    cp app/*.py app/requirements.txt "$APP_DIR"/
    rm -rf "$APP_DIR/assets"
    cp -r app/assets "$APP_DIR"/
  fi

  "$PYTHON_BIN" -m venv "$APP_DIR/.venv"
  "$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
  "$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
  ok "код в $APP_DIR, зависимости установлены"

  # токен и настройки — в отдельный env-файл, который читает systemd
  {
    echo "BOT_TOKEN=$BOT_TOKEN"
    [ -n "${DEMO_MODE:-}" ]          && echo "DEMO_MODE=$DEMO_MODE"
    [ -n "${PRICE_STARS:-}" ]        && echo "PRICE_STARS=$PRICE_STARS"
    [ -n "${OLD_PRICE_STARS:-}" ]    && echo "OLD_PRICE_STARS=$OLD_PRICE_STARS"
    [ -n "${PRODUCT_NAME:-}" ]       && echo "PRODUCT_NAME=$PRODUCT_NAME"
    [ -n "${SERVICE_NAME:-}" ]       && echo "SERVICE_NAME=$SERVICE_NAME"
    [ -n "${SERVICE_URL:-}" ]        && echo "SERVICE_URL=$SERVICE_URL"
    [ -n "${SERVICE_AGENT_URL:-}" ]  && echo "SERVICE_AGENT_URL=$SERVICE_AGENT_URL"
    [ -n "${FREE_USERNAMES:-}" ]     && echo "FREE_USERNAMES=$FREE_USERNAMES"
    [ -n "${FREE_USER_IDS:-}" ]      && echo "FREE_USER_IDS=$FREE_USER_IDS"
    [ -n "${ADMIN_IDS:-}" ]          && echo "ADMIN_IDS=$ADMIN_IDS"
    [ -n "${ADMIN_USERNAMES:-}" ]    && echo "ADMIN_USERNAMES=$ADMIN_USERNAMES"
    [ -n "${REVIEWS_URL:-}" ]        && echo "REVIEWS_URL=$REVIEWS_URL"
    [ -n "${SUPPORT_URL:-}" ]        && echo "SUPPORT_URL=$SUPPORT_URL"
    [ -n "${CHANNEL_URL:-}" ]        && echo "CHANNEL_URL=$CHANNEL_URL"
  } > "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  install -d -o arena -g arena -m 700 "$APP_DIR/data"
  chown -R arena:arena "$APP_DIR"
  ok "настройки в $APP_DIR/.env"

  sed "s|/opt/arena-store|$APP_DIR|g; s|User=www-data|User=arena|g" arena-store.service > /etc/systemd/system/$SERVICE_NAME.service
  systemctl daemon-reload
  systemctl enable $SERVICE_NAME
  systemctl restart $SERVICE_NAME
  sleep 2
  systemctl --no-pager --lines=5 status $SERVICE_NAME || true
  ok "сервис $SERVICE_NAME запущен"
  echo
  echo "  логи:    journalctl -u $SERVICE_NAME -f"
  echo "  рестарт: systemctl restart $SERVICE_NAME"
else
  fail "Неизвестный режим: $MODE (доступно: docker | systemd)"
fi
