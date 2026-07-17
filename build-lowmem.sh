#!/usr/bin/env bash
# Последовательная сборка для слабых серверов (≈1 ГБ RAM и меньше).
#
# Зачем: `docker compose build` собирает все сервисы ПАРАЛЛЕЛЬНО. На 0.6 ГБ три
# сборки одновременно выедают память, и ядро убивает процесс (OOM, "Killed",
# exit 137). Здесь они идут по одной, а между ними чистится мусор.
#
# Запуск:  bash build-lowmem.sh

set -uo pipefail

COMPOSE="docker compose -p obshaga -f docker-compose.prod.yml"

echo
echo "=== Память ==="
free -h 2>/dev/null || echo "  (free недоступен)"

swap_kb=$(awk '/SwapTotal/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)
if [ "${swap_kb:-0}" -lt 1000000 ]; then
	echo
	echo "  ВНИМАНИЕ: swap меньше 1 ГБ ($((swap_kb / 1024)) МБ)."
	echo "  На слабом сервере сборка фронтенда почти наверняка упадёт с OOM."
	echo "  Сделай swap и запусти скрипт заново:"
	echo
	echo "    fallocate -l 2G /swapfile && chmod 600 /swapfile"
	echo "    mkswap /swapfile && swapon /swapfile"
	echo "    echo '/swapfile none swap sw 0 0' >> /etc/fstab"
	echo
	read -r -p "  Всё равно продолжить? [y/N] " answer
	case "$answer" in
	[yY]) ;;
	*) exit 1 ;;
	esac
fi

# Порядок намеренный: фронтенд самый прожорливый — собираем его последним,
# когда остальные образы уже готовы и ничего не мешает.
for svc in backend bot frontend; do
	echo
	echo "=== Собираю $svc ==="
	if ! $COMPOSE build "$svc"; then
		echo
		echo "  Сборка $svc упала."
		echo "  Если в логе 'Killed' или exit 137 — не хватило памяти:"
		echo "  добавь swap (команды выше) и запусти скрипт заново."
		exit 1
	fi
	# Промежуточные слои занимают место и память под кэш — подчищаем.
	docker builder prune -f --filter until=24h >/dev/null 2>&1 || true
done

echo
echo "=== Готово. Все образы собраны. Поднимай: ==="
echo
echo "  $COMPOSE --profile bot up -d"
echo
