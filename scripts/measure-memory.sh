#!/usr/bin/env bash
# Sidebay 内存基线测量：本地与 flatpak 分别启动，15s 后读 VmRSS。
# 用法: ./scripts/measure-memory.sh [local|flatpak|all]
set -e
cd "$(dirname "$0")/.."

measure() {
    local label="$1" pid
    sleep 15
    for p in $(pgrep -f "$2" 2>/dev/null | head -3); do
        local comm rss
        comm=$(cat /proc/$p/comm 2>/dev/null || echo "?")
        rss=$(awk '/VmRSS/{print $2}' /proc/$p/status 2>/dev/null || echo 0)
        [ -n "$rss" ] && [ "$rss" -gt 5000 ] && echo "$label: $comm RSS=$((rss/1024))MB"
    done
}

case "${1:-all}" in
    local)
        pkill -f "\.venv/bin/python3 .*sidebay" 2>/dev/null || true
        (timeout 40 ./run.sh > /tmp/sb_mem_local.log 2>&1 &)
        measure "本地" "\.venv/bin/python3 .*sidebay"
        ;;
    flatpak)
        flatpak kill org.sidebay.SideBay 2>/dev/null || true
        (timeout 40 flatpak run org.sidebay.SideBay > /tmp/sb_mem_fp.log 2>&1 &)
        measure "flatpak" "python3 -m sidebay"
        ;;
    all)
        "$0" local
        "$0" flatpak
        ;;
esac
