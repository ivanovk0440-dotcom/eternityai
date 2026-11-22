#!/usr/bin/env bash
# Обновление магазина на сервере: код, гайд, обложка — без потери базы заказов.
#
#   ./update.sh            # перезалить код из app/ и перезапустить
#   ./update.sh --db-backup  # сначала сделать резервную копию базы
#
# Работает и для docker, и для systemd (режим определяется по наличию контейнера).

set -euo pipefail

cd "$(dirname "$0")"
SERVICE_NAME="arena-store"
APP_DIR="${APP_DIR:-/opt/arena-store}"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
fail() { printf '  \033[31m✗\033[0m %s\n' "$*"; exit 1; }

bold "▸ Обновление магазина"

if [ "${1:-}" = "--db-backup" ] || [ -f data/shop.db ]; then
  STAMP=$(date +%Y-%m-%d_%H-%M)
  mkdir -p backups
  if [ -f data/shop.db ]; then
    cp data/shop.db "backups/shop_$STAMP.db" && ok "Резервная копия: backups/shop_$STAMP.db"
  fi
  if command -v sqlite3 >/dev/null 2>&1 && [ -f data/shop.db ]; then
    sqlite3 data/shop.db ".backup 'backups/shop_$STAMP.sql'" 2>/dev/null || true
  fi
fi

if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "arena-store"; then
  ok "Обнаружен контейнер arena-store — обновляю через Docker"
  docker compose build
  docker compose up -d
  docker compose ps
  ok "Контейнер перезапущен с новым кодом"
else
  ok "Обновляю через systemd"
  [ -d "$APP_DIR" ] || fail "Каталог $APP_DIR не найден. Сначала запустите ./install.sh systemd"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete --exclude 'data' --exclude '.env' --exclude '__pycache__' app/ "$APP_DIR"/
  else
    warn "rsync не найден — копирую вручную"
    find "$APP_DIR" -maxdepth 1 -name '*.py' -delete
    cp app/*.py app/requirements.txt "$APP_DIR"/
    rm -rf "$APP_DIR/assets"
    cp -r app/assets "$APP_DIR"/
  fi
  chown -R arena:arena "$APP_DIR"
  systemctl restart $SERVICE_NAME
  sleep 2
  systemctl --no-pager --lines=8 status $SERVICE_NAME || true
  ok "Сервис перезапущен"
fi

echo
echo "Логи:  docker compose logs -f  |  journalctl -u $SERVICE_NAME -f"
