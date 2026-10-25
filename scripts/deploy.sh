#!/usr/bin/env bash
# SMY Agent — deploy / update on cPanel (hostmaster.uz). Safe to run again and again.
#
#   bash ~/smyagent/scripts/deploy.sh            # pull main, install, backup, migrate, restart, check
#   bash ~/smyagent/scripts/deploy.sh --no-pull  # use the code already on the server
#
# Optional environment: VENV=~/virtualenv/smyagent/3.12  BACKUP_DIR=~/smyagent_data/backups
# Messages are in Uzbek for the owner. Secrets are never printed.

set -euo pipefail
DEPLOY_LOCK=""

main() {
  local app_dir pull=1 health=1
  app_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  for arg in "$@"; do
    case "$arg" in
      --no-pull) pull=0 ;;
      --skip-health) health=0 ;;
      -h|--help) sed -n '2,8p' "${BASH_SOURCE[0]}"; return 0 ;;
      *) fail "Noma'lum parametr: $arg" ;;
    esac
  done

  local venv="${VENV:-$HOME/virtualenv/$(basename "$app_dir")/3.12}"
  local py="$venv/bin/python"
  local backup_dir="${BACKUP_DIR:-$HOME/smyagent_data/backups}"
  local log_dir="$HOME/smyagent_data"
  mkdir -p "$log_dir" "$app_dir/tmp"
  chmod 700 "$log_dir"
  # Log to deploy.log as well as the screen. No process substitution (`>(tee …)`):
  # CageFS on shared hosting has no /dev/fd, so re-run ourselves through a plain pipe.
  if [[ -z "${SMY_DEPLOY_LOGGING:-}" ]]; then
    export SMY_DEPLOY_LOGGING=1
    local status=0
    bash "${BASH_SOURCE[0]}" "$@" 2>&1 | tee -a "$log_dir/deploy.log" || status=$?
    # pipefail: status is the script's own exit code unless tee itself failed.
    return "$status"
  fi
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') deploy boshlandi ($app_dir)"

  # Only one deploy at a time.
  DEPLOY_LOCK="$app_dir/tmp/deploy.lock"
  if ! mkdir "$DEPLOY_LOCK" 2>/dev/null; then
    fail "Boshqa deploy ishlayapti (yoki to'xtab qolgan). 10 daqiqa kuting yoki: rmdir $DEPLOY_LOCK"
  fi
  trap 'rmdir "$DEPLOY_LOCK" 2>/dev/null || true' EXIT

  step "1/8 Tekshiruv"
  [[ -x "$py" ]] || fail "Virtualenv topilmadi: $venv
   cPanel → Setup Python App da Python 3.12 ilovasini yarating (Application root: $(basename "$app_dir")).
   Boshqa yo'l bo'lsa: VENV=/to'liq/yo'l bash scripts/deploy.sh"
  [[ -f "$app_dir/.env" ]] || fail ".env yo'q. Avval bajaring:
   cd $app_dir && $py scripts/setup_env.py"
  chmod 600 "$app_dir/.env"
  cd "$app_dir"
  ok "Python: $("$py" --version 2>&1), ilova: $app_dir"

  step "2/8 Kod (GitHub main)"
  if [[ $pull -eq 1 ]]; then
    # cPanel may rewrite the startup file when the app is (re)created: restore ours.
    if ! git diff --quiet -- passenger_wsgi.py 2>/dev/null; then
      git checkout -- passenger_wsgi.py
      warn "passenger_wsgi.py cPanel tomonidan o'zgartirilgan edi — asl holiga qaytarildi."
    fi
    if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
      git status --short --untracked-files=no
      fail "Serverdagi kod qo'lda o'zgartirilgan (yuqoridagi fayllar). Deploy to'xtatildi — hech narsa buzilmadi."
    fi
    git fetch --quiet origin main
    git merge --ff-only --quiet origin/main || fail "main bilan birlashmadi (fast-forward emas)."
  fi
  ok "Versiya: $(git log -1 --format='%h %s' | cut -c1-70)"

  step "3/8 Kutubxonalar (pip)"
  "$py" -m pip install --quiet --disable-pip-version-check --upgrade pip
  "$py" -m pip install --quiet --disable-pip-version-check .
  ok "O'rnatildi"

  step "4/8 Sozlamalar va baza"
  "$py" -m app.cli check-config || fail "Sozlama yoki bazada xato (yuqoridagi xabar). .env ni tekshiring:
   $py scripts/setup_env.py --set DATABASE_URL"

  step "5/8 Zaxira nusxa (backup)"
  "$py" -m app.cli db-backup --dir "$backup_dir" --keep 14 || fail "Zaxira olinmadi — migratsiya qilinmadi (ma'lumot xavfsiz)."

  step "6/8 Migratsiya"
  "$py" -m alembic upgrade head
  ok "Baza versiyasi: $("$py" -m alembic current 2>/dev/null | tail -1)"

  step "7/8 Qayta ishga tushirish"
  touch "$app_dir/tmp/restart.txt"
  ok "tmp/restart.txt yangilandi (Passenger keyingi so'rovda yangi kodni yuklaydi)"

  step "8/8 Sayt tekshiruvi"
  if [[ $health -eq 1 ]]; then
    local base
    base="$("$py" -c 'from app.core.config import get_settings; print(get_settings().app_base_url.rstrip("/"))')"
    local tries=0
    until curl -fsS --max-time 20 "$base/api/v1/health" >/dev/null 2>&1; do
      tries=$((tries + 1))
      [[ $tries -ge 6 ]] && fail "$base/api/v1/health javob bermadi.
   cPanel → Setup Python App → ilovani RESTART qiling, so'ng: bash scripts/deploy.sh --no-pull"
      sleep 5
    done
    curl -fsS --max-time 20 "$base/api/v1/ready" >/dev/null 2>&1 || fail "$base/api/v1/ready: baza ulanmadi."
    ok "$base ishlayapti ✅"
  else
    warn "Sayt tekshiruvi o'tkazib yuborildi (--skip-health)"
  fi
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') deploy tugadi ✅"
}

step() { printf '\n▶ %s\n' "$1"; }
ok() { printf '  ✓ %s\n' "$1"; }
warn() { printf '  ⚠ %s\n' "$1"; }
fail() { printf '\n  ✗ %s\n' "$1" >&2; exit 1; }

main "$@"
