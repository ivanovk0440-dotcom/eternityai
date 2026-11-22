#!/usr/bin/env bash
# Установка магазина на сервер из GitHub.
# Токен и настройки — из переменных окружения сервера.
#
#   export BOT_TOKEN=123456:AA...
#   bash <(curl -fsSL https://raw.githubusercontent.com/<аккаунт>/<репозиторий>/main/setup.sh)
#
# Скачивает код (git или tarball), затем вызывает install.sh.

set -euo pipefail

REPO="${REPO:-<аккаунт>/<репозиторий>}"
BASE_URL="${BASE_URL:-https://github.com}"
MODE="${1:-docker}"
DIR="${DIR:-arena-store}"
BRANCH="${BRANCH:-main}"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
fail() { printf '  \033[31m✗\033[0m %s\n' "$*"; exit 1; }

bold "▸ Установка Arena Store"
bold "  репозиторий: $REPO"
bold "  режим:       $MODE"

[ -n "${BOT_TOKEN:-}" ] || fail "Нет BOT_TOKEN. Выполните: export BOT_TOKEN=123456:AA..."

TARGET="$HOME/$DIR"
mkdir -p "$TARGET"
cd "$TARGET"

# ---------------------------------------------------------------- скачать код
fetched=""
download_tarball() {
  command -v curl >/dev/null 2>&1 || { fail "Нужен git или curl. Поставьте: apt install -y git"; return 1; }
  command -v tar  >/dev/null 2>&1 || { fail "Нужен tar"; return 1; }
  local url="$BASE_URL/$REPO/archive/refs/heads/$BRANCH.tar.gz"
  echo "  качаю $url"
  curl -fsSL "$url" -o /tmp/repo.tar.gz || { fail "Не удалось скачать $url"; return 1; }
  local tmp; tmp=$(mktemp -d)
  tar -xzf /tmp/repo.tar.gz -C "$tmp" || { rm -rf "$tmp"; fail "Не удалось распаковать"; return 1; }
  local top; top=$(find "$tmp" -mindepth 1 -maxdepth 1 -type d | head -1)
  if [ -n "$top" ] && [ -f "$top/install.sh" ]; then cp -a "$top"/. "$TARGET"/; else cp -a "$tmp"/. "$TARGET"/; fi
  rm -rf "$tmp" /tmp/repo.tar.gz
  fetched="tarball"
}

if command -v git >/dev/null 2>&1; then
  if [ -d .git ]; then
    git pull --ff-only >/dev/null 2>&1 && fetched="git pull" || fetched="уже актуально"
  elif git clone --depth 1 -b "$BRANCH" "$BASE_URL/$REPO.git" . >/dev/null 2>&1; then
    fetched="git clone"
  else
    echo "  git clone не сработал — пробую tarball"
    download_tarball || exit 1
  fi
else
  echo "  git не установлен — качаю tarball"
  download_tarball || exit 1
fi

[ -f install.sh ] || fail "Не найден install.sh — репозиторий скачался не полностью?"
[ -f app/assets/guide.pdf ] || fail "Нет app/assets/guide.pdf — репозиторий повреждён."
ok "код получен ($fetched) → $TARGET"

chmod +x install.sh update.sh backup.sh 2>/dev/null || true
./install.sh "$MODE"

echo
bold "Готово."
echo "  cd $TARGET"
echo "  docker compose logs -f        # логи (docker)"
echo "  journalctl -u arena-store -f   # логи (systemd)"
echo "  ./update.sh --db-backup        # обновить код или гайд"
echo "  ./backup.sh                    # резервная копия базы"
