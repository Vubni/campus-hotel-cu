#!/usr/bin/env bash
# Проверка перед первым запуском на сервере.
#
# Смысл: Let's Encrypt разрешает всего 5 неудачных попыток в час на домен.
# Если запустить стек с непрописанным DNS или закрытым портом, попытки сгорят,
# и придётся ждать. Этот скрипт проверяет всё заранее и ничего не запускает.
#
# Запуск:  bash preflight.sh

set -uo pipefail

ok=0
fail=0
say_ok()   { printf "  \033[32mOK\033[0m    %s\n" "$1"; ok=$((ok + 1)); }
say_fail() { printf "  \033[31mПРОБЛЕМА\033[0m %s\n" "$1"; fail=$((fail + 1)); }
say_warn() { printf "  \033[33m?\033[0m     %s\n" "$1"; }

echo
echo "=== 1. Файл .env ==="
if [ ! -f .env ]; then
	say_fail ".env не найден. Сделай: cp .env.example .env && nano .env"
	echo
	echo "Дальше проверять нечего."
	exit 1
fi
set -a
# shellcheck disable=SC1091
. ./.env
set +a

for var in TELEGRAM_BOT_TOKEN TELEGRAM_BOT_USERNAME BOT_SECRET POSTGRES_PASSWORD DOMAIN; do
	if [ -z "${!var:-}" ]; then
		say_fail "$var пустой — заполни в .env"
	else
		say_ok "$var задан"
	fi
done

case "${DOMAIN:-}" in
*://* | */*) say_fail "DOMAIN=$DOMAIN — нужен голый домен, без https:// и без слэша" ;;
esac

echo
echo "=== 2. DNS: домен смотрит на этот сервер? ==="
server_ip=$(curl -s --max-time 10 https://api.ipify.org || echo "")
domain_ip=$(getent hosts "${DOMAIN:-}" 2>/dev/null | awk '{print $1}' | head -1)
[ -z "$domain_ip" ] && domain_ip=$(dig +short "${DOMAIN:-}" 2>/dev/null | tail -1)

if [ -z "$server_ip" ]; then
	say_warn "не удалось узнать внешний IP сервера — проверь DNS вручную"
elif [ -z "$domain_ip" ]; then
	say_fail "$DOMAIN никуда не резолвится. Добавь A-запись → $server_ip и подожди"
elif [ "$domain_ip" = "$server_ip" ]; then
	say_ok "$DOMAIN → $domain_ip (совпадает с IP сервера)"
else
	say_fail "$DOMAIN → $domain_ip, а сервер имеет $server_ip. Сертификат не выдастся"
	say_warn "если домен за проксёй Cloudflare (оранжевое облако) — выключи её"
fi

echo
echo "=== 3. Порты 80 и 443 свободны? ==="
# Caddy не поднимется, если порты занял другой nginx/apache.
for port in 80 443; do
	busy=$(ss -tlnp 2>/dev/null | awk -v p=":$port" '$4 ~ p"$" {print $6}' | head -1)
	if [ -n "$busy" ]; then
		say_fail "порт $port занят: $busy — останови (systemctl stop nginx / apache2)"
	else
		say_ok "порт $port свободен"
	fi
done

echo
echo "=== 4. Порты открыты снаружи? ==="
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
	for port in 80 443; do
		if ufw status | grep -qE "^$port(/tcp)?\s+ALLOW"; then
			say_ok "ufw пропускает $port"
		else
			say_fail "ufw не пропускает $port — сделай: ufw allow $port/tcp"
		fi
	done
else
	say_warn "ufw выключен или не установлен — проверь firewall в панели хостера"
fi
say_warn "порт 80 нужен именно для выдачи сертификата, не только 443"

echo
echo "=== 5. Docker ==="
if docker compose version >/dev/null 2>&1; then
	say_ok "docker compose на месте"
else
	say_fail "нет docker compose — curl -fsSL https://get.docker.com | sh"
fi

echo
if [ "$fail" -eq 0 ]; then
	printf "\033[32mВсё готово (%d проверок).\033[0m Запускай:\n\n" "$ok"
	echo "  docker compose -p obshaga -f docker-compose.prod.yml --profile bot up -d --build"
	echo
	exit 0
fi

printf "\033[31mПроблем: %d.\033[0m Почини их до запуска — иначе сгорят попытки Let's Encrypt.\n\n" "$fail"
exit 1
