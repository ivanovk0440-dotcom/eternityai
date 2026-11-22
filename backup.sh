#!/usr/bin/env bash
# Резервное копирование: база заказов + PDF-гайд.
#
#   ./backup.sh              # копия в ./backups
#   ./backup.sh /var/backups # копия в другую папку
#
# Для cron:  0 3 * * *  /opt/arena-store/backup.sh /var/backups/arena-store

set -euo pipefail
cd "$(dirname "$0")"

DEST="${1:-backups}"
STAMP=$(date +%Y-%m-%d_%H-%M)
mkdir -p "$DEST"

if [ -f data/shop.db ]; then
  if command -v sqlite3 >/dev/null 2>&1; then
    # согласованная копия даже при работающем боте
    sqlite3 data/shop.db ".backup '$DEST/shop_$STAMP.db'"
  else
    cp data/shop.db "$DEST/shop_$STAMP.db"
  fi
  echo "✓ $DEST/shop_$STAMP.db"
else
  echo "! база не найдена (data/shop.db) — пропускаю"
fi

if [ -f app/assets/guide.pdf ]; then
  cp app/assets/guide.pdf "$DEST/guide_$STAMP.pdf"
  echo "✓ $DEST/guide_$STAMP.pdf"
fi

# храним последние 30 копий
if [ -d "$DEST" ]; then
  ls -1t "$DEST"/shop_*.db 2>/dev/null | tail -n +31 | xargs -r rm -f
  ls -1t "$DEST"/guide_*.pdf 2>/dev/null | tail -n +31 | xargs -r rm -f
fi
echo "✓ копий в $DEST: $(ls -1 "$DEST" 2>/dev/null | wc -l)"
