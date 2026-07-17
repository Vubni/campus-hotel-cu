# Деплой на VPS с доменом cu.vubni.com

Инструкция с нуля: чистый Ubuntu-сервер → работающий сайт с HTTPS и ботом.
Везде подставляй свой домен, если он отличается от `cu.vubni.com`.

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
- домен `cu.vubni.com` и доступ к его DNS;
- токен бота из [@BotFather](https://t.me/BotFather) (`/newbot`).

---

## 1. Направить домен на сервер

В панели DNS добавь A-запись:

| Тип | Имя  | Значение          | TTL |
| --- | ---- | ----------------- | --- |
| A   | `cu` | `<IP твоего VPS>` | 300 |

> Имя пишем `cu`, а не `cu.vubni.com` — панель сама допишет зону. Если она
> требует полное имя, укажи `cu.vubni.com`.

Проверь, что запись разошлась (это может занять от минуты до пары часов):

```bash
dig +short cu.vubni.com
# должен вывести IP твоего VPS
```

**Не переходи к шагу 5, пока команда не покажет верный IP.** Caddy запросит
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
SITE_URL=https://cu.vubni.com
```

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

## 6. Проверить домен в Caddyfile

Если домен не `cu.vubni.com`, поправь первую строку:

```bash
nano Caddyfile
```

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

Открой `https://cu.vubni.com` — сертификат Caddy получит сам за 10–30 секунд.
Если браузер ругается на сертификат, посмотри логи:

```bash
docker compose -p obshaga -f docker-compose.prod.yml logs caddy | tail -30
```

---

## 8. Настроить бота в BotFather

Без этого шага кнопка «Войти через Telegram» работать не будет — виджет
запускается только на домене, который явно разрешён боту.

В [@BotFather](https://t.me/BotFather):

1. `/setdomain` → выбери бота → отправь `cu.vubni.com`
2. `/setmenubutton` → выбери бота → отправь `https://cu.vubni.com` → задай
   подпись кнопки, например «Найти соседа» — это включит Mini App внутри
   Telegram.

Вебхук настраивать не нужно: бот работает на long polling и сам ходит в
Telegram за обновлениями.

---

## 9. Проверить, что всё живо

```bash
curl -s https://cu.vubni.com/api/health
# {"status":"ok"}

curl -s https://cu.vubni.com/api/config
# telegram_enabled должно быть true — значит токен и ник бота подхватились
```

Дальше руками:

1. Открой сайт → выбери пол → «Разместить анкету» → должна быть кнопка
   «Войти через Telegram» (если её нет — проверь `/setdomain` и `api/config`);
2. Напиши боту `/start` — он должен ответить и привязать твою анкету;
3. Подай заявку в компанию с другого аккаунта — участникам прилетит уведомление.

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
| Сайт не открывается                    | `dig +short cu.vubni.com` — верный ли IP; открыты ли 80/443 (`ufw status` и firewall у хостера) |
| Ошибка сертификата                     | `logs caddy`. Чаще всего домен ещё не разошёлся или 80-й порт закрыт                          |
| Нет кнопки «Войти через Telegram»      | `/api/config` вернул `telegram_enabled: false` → не заполнен `.env`; либо не сделан `/setdomain` |
| Кнопка есть, но пишет «Bot domain invalid» | В `/setdomain` указан не тот домен                                                          |
| Бот молчит                             | `logs bot`. Обычно неверный `TELEGRAM_BOT_TOKEN` или бот запущен ещё где-то (два polling'а конфликтуют) |
| Бот не может голосовать                | `BOT_SECRET` в `.env` разъехался — он должен быть один и тот же (оба контейнера читают одну переменную) |
| Фото не загружаются                    | `logs backend`; лимит — 5 МБ, nginx пропускает до 8 МБ                                        |

---

## Чего здесь сознательно нет

- **Авторизации по анкетам.** «Моя анкета» — это id в `localStorage` браузера.
  Для друзей по общаге хватает, но технически подкованный человек может дёрнуть
  API с чужим `profile_id`. Если сервис выйдет за пределы своих — сюда нужна
  нормальная авторизация (проще всего — только через Telegram-вход).
- **CORS.** Бэкенд отвечает `allow_origins=["*"]`. В проде фронт и API живут на
  одном домене, так что это не используется, но лучше сузить до своего домена.
- **Автобэкапа.** Команды выше стоит завернуть в cron.
