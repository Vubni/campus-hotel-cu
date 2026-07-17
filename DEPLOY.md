# Деплой на VPS с доменом disk.cu-politic.ru

Инструкция с нуля: чистый Ubuntu-сервер → работающий сайт с HTTPS и ботом.
Везде подставляй свой домен, если он отличается от `disk.cu-politic.ru`.

Что получится в итоге:

```
интернет → :443 Caddy (HTTPS) → frontend (nginx) ─┬─ статика React
                                                   └─ /api → backend → Postgres
                                        bot ── long polling → Telegram
```

Наружу открыт только Caddy. База, бэкенд и бот живут во внутренней сети Docker
и снаружи недоступны.

---

## 0. Что нужно заранее

- VPS с Ubuntu 22.04/24.04 и root-доступом (хватит 1 CPU / 1 ГБ RAM);
- домен `disk.cu-politic.ru` и доступ к его DNS;
- токен бота из [@BotFather](https://t.me/BotFather) (`/newbot`).

---

## 1. Направить домен на сервер

В панели DNS добавь A-запись:

| Тип | Имя  | Значение          | TTL |
| --- | ---- | ----------------- | --- |
| A   | `disk` | `<IP твоего VPS>` | 300 |

> Имя пишем `disk`, а не `disk.cu-politic.ru` — панель сама допишет зону
> `cu-politic.ru`. Если она требует полное имя, укажи `disk.cu-politic.ru`.

Проверь, что запись разошлась (это может занять от минуты до пары часов):

```bash
dig +short disk.cu-politic.ru
# должен вывести IP твоего VPS
```

**Не переходи к шагу 7, пока команда не покажет верный IP.** Caddy запросит
сертификат, Let's Encrypt постучится на домен — и если он ведёт не туда,
выдача сертификата упрётся в лимиты.

---

## 2. Установить Docker

На сервере под root:

```bash
apt update && apt upgrade -y
curl -fsSL https://get.docker.com | sh
docker --version && docker compose version
```

---

## 3. Открыть порты

```bash
ufw allow 22/tcp     # ssh — сделай это ПЕРВЫМ, иначе отрежешь себе доступ
ufw allow 80/tcp     # нужен для выдачи сертификата
ufw allow 443/tcp    # https
ufw --force enable
ufw status
```

Если у провайдера (Timeweb, Selectel, Hetzner) есть свой firewall в панели —
открой 80 и 443 ещё и там.

---

## 4. Забрать код

```bash
apt install -y git
git clone https://github.com/<твой-логин>/<твой-репозиторий>.git /opt/campus
cd /opt/campus
```

---

## 5. Заполнить секреты

```bash
cp .env.example .env
nano .env
```

Заполни так:

```ini
TELEGRAM_BOT_TOKEN=123456789:AA...   # из @BotFather
TELEGRAM_BOT_USERNAME=my_campus_bot  # ник бота без @
BOT_SECRET=<вставь результат первой команды ниже>
POSTGRES_PASSWORD=<вставь результат второй>
DOMAIN=disk.cu-politic.ru            # без https:// и без слэша
```

`DOMAIN` задаётся один раз: на него Caddy выпускает сертификат, из него же
собирается адрес в ссылках бота. Менять домен нужно только здесь.
`SITE_URL` в проде не используется — он только для локального запуска.

Секреты сгенерируй прямо на сервере:

```bash
openssl rand -hex 32   # → BOT_SECRET
openssl rand -hex 16   # → POSTGRES_PASSWORD
```

`BOT_SECRET` и `POSTGRES_PASSWORD` к Telegram отношения не имеют — это твои
собственные пароли: первый закрывает служебные ручки бота от посторонних,
второй защищает базу. Придумывать «правильное» значение не нужно, просто вставь
случайную строку.

Файл `.env` в git не попадает — он в `.gitignore`.

---

## 6. Проверить готовность (важно)

```bash
bash preflight.sh
```

Скрипт проверяет ровно то, из-за чего обычно не появляется SSL: заполнен ли
`.env`, смотрит ли домен на этот сервер, свободны и открыты ли порты 80/443.

**Не запускай стек, пока он не скажет «Всё готово».** Let's Encrypt даёт всего
5 неудачных попыток в час на домен: если стартовать с непрописанным DNS, попытки
сгорят, и придётся ждать час.

---

## 7. Запустить

```bash
docker compose -p obshaga -f docker-compose.prod.yml --profile bot up -d --build
```

Первая сборка займёт несколько минут. Дальше:

```bash
docker compose -p obshaga -f docker-compose.prod.yml ps
# все сервисы должны быть Up, db — healthy
```

Открой `https://disk.cu-politic.ru` — сертификат Caddy получит сам за 10–30 секунд.
Если браузер ругается на сертификат, посмотри логи:

```bash
docker compose -p obshaga -f docker-compose.prod.yml logs caddy | tail -30
```

---

## 8. Настроить бота в BotFather

Без этого шага кнопка «Войти через Telegram» работать не будет — виджет
запускается только на домене, который явно разрешён боту.

В [@BotFather](https://t.me/BotFather):

1. `/setdomain` → выбери бота → отправь `disk.cu-politic.ru`
2. `/setmenubutton` → выбери бота → отправь `https://disk.cu-politic.ru` → задай
   подпись кнопки, например «Найти соседа» — это включит Mini App внутри
   Telegram.

Вебхук настраивать не нужно: бот работает на long polling и сам ходит в
Telegram за обновлениями.

---

## 9. Проверить, что всё живо

```bash
curl -s https://disk.cu-politic.ru/api/health
# {"status":"ok"}

curl -s https://disk.cu-politic.ru/api/config
# telegram_enabled должно быть true — значит токен и ник бота подхватились
```

Дальше руками:

1. Открой сайт → замок в адресной строке должен быть закрыт (это и есть SSL);
2. Выбери пол → «Разместить анкету» → должна быть кнопка «Войти через
   Telegram» (если её нет — проверь `/setdomain` и `api/config`);
3. Напиши боту `/start` — он должен ответить и привязать твою анкету;
4. Подай заявку в компанию с другого аккаунта — участникам прилетит уведомление.

---

## Про SSL

**Покупать и ставить сертификат не нужно.** Caddy при первом старте сам получает
его у Let's Encrypt, сам продлевает каждые ~60 дней и сам редиректит `http` →
`https`. В панели регистратора никакой «SSL» заказывать не надо — там нужна
только A-запись. Сертификаты лежат в томе `caddy_data` и переживают
пересборку и перезапуск.

Проверить, что сертификат выпустился:

```bash
docker compose -p obshaga -f docker-compose.prod.yml logs caddy | grep -i "certificate obtained"
# certificate obtained successfully

echo | openssl s_client -connect disk.cu-politic.ru:443 -servername disk.cu-politic.ru 2>/dev/null \
  | openssl x509 -noout -issuer -dates
# issuer=... Let's Encrypt ...  и срок действия
```

Если сертификата нет, причина почти всегда одна из четырёх:

| Причина                             | Как увидеть                                          | Что делать                                             |
| ----------------------------------- | ---------------------------------------------------- | ------------------------------------------------------ |
| DNS не смотрит на сервер            | `bash preflight.sh`                                  | Поправить A-запись, дождаться `dig`                    |
| Закрыт порт 80                      | `ufw status`, firewall хостера                        | `ufw allow 80/tcp` — 80 нужен для проверки, не только 443 |
| Порт занят другим nginx/apache      | `ss -tlnp \| grep :80`                                | `systemctl stop nginx` (или `apache2`), затем `disable` |
| Домен за проксёй Cloudflare         | В DNS оранжевое облако                                | Выключить проксирование (серое облако)                  |

Сожжённые попытки Let's Encrypt (5 неудач в час) не чинятся ничем, кроме
ожидания — поэтому и нужен `preflight.sh` до первого запуска.

---

## Эксплуатация

**Логи:**

```bash
cd /opt/campus
docker compose -p obshaga -f docker-compose.prod.yml logs -f backend
docker compose -p obshaga -f docker-compose.prod.yml logs -f bot
```

**Обновить после пуша в GitHub:**

```bash
cd /opt/campus
git pull
docker compose -p obshaga -f docker-compose.prod.yml --profile bot up -d --build
```

Данные переживают пересборку: они в томах `pgdata` (база) и `uploads` (фото).

**Бэкап базы и фото:**

```bash
cd /opt/campus
docker compose -p obshaga -f docker-compose.prod.yml exec -T db \
  pg_dump -U obshaga obshaga | gzip > ~/backup-$(date +%F).sql.gz

docker run --rm -v obshaga_uploads:/data -v ~:/out alpine \
  tar czf /out/uploads-$(date +%F).tar.gz -C /data .
```

**Восстановить базу:**

```bash
gunzip -c ~/backup-2026-07-17.sql.gz | docker compose -p obshaga \
  -f docker-compose.prod.yml exec -T db psql -U obshaga -d obshaga
```

**Остановить:**

```bash
docker compose -p obshaga -f docker-compose.prod.yml down          # данные целы
docker compose -p obshaga -f docker-compose.prod.yml down -v       # стереть всё
```

---

## Если что-то не работает

| Симптом                                | Куда смотреть                                                                                |
| -------------------------------------- | -------------------------------------------------------------------------------------------- |
| Сайт не открывается                    | `dig +short disk.cu-politic.ru` — верный ли IP; открыты ли 80/443 (`ufw status` и firewall у хостера) |
| Ошибка сертификата                     | `logs caddy`. Чаще всего домен ещё не разошёлся или 80-й порт закрыт                          |
| Нет кнопки «Войти через Telegram»      | `/api/config` вернул `telegram_enabled: false` → не заполнен `.env`; либо не сделан `/setdomain` |
| Кнопка есть, но пишет «Bot domain invalid» | В `/setdomain` указан не тот домен                                                          |
| Бот молчит                             | `logs bot`. Обычно неверный `TELEGRAM_BOT_TOKEN` или бот запущен ещё где-то (два polling'а конфликтуют) |
| Бот не может голосовать                | `BOT_SECRET` в `.env` разъехался — он должен быть один и тот же (оба контейнера читают одну переменную) |
| Фото не загружаются                    | `logs backend`; лимит — 5 МБ, nginx пропускает до 8 МБ                                        |
| Сменил домен — половина работает по-старому | Домен задан только через `DOMAIN` в `.env`. После правки: `up -d --build` и заново `/setdomain` в BotFather |

---

## Чего здесь сознательно нет

- **Авторизации по анкетам.** «Моя анкета» — это id в `localStorage` браузера.
  Для друзей по общаге хватает, но технически подкованный человек может дёрнуть
  API с чужим `profile_id`. Если сервис выйдет за пределы своих — сюда нужна
  нормальная авторизация (проще всего — только через Telegram-вход).
- **CORS.** Бэкенд отвечает `allow_origins=["*"]`. В проде фронт и API живут на
  одном домене, так что это не используется, но лучше сузить до своего домена.
- **Автобэкапа.** Команды выше стоит завернуть в cron.
