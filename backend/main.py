from datetime import datetime
from typing import List, Optional

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, text
from sqlalchemy.orm import Session

import admin_export
import campuses
import config
import join_flow
import models
import notifier
import schemas
import storage
import telegram_auth
from database import Base, engine, get_db, wait_for_db

app = FastAPI(title="Кампус-отели Диск и Облако — поиск соседей", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== Авторизация по подписи Telegram =====
# Все заходят через бота, поэтому в каждом запросе есть initData — строка,
# подписанная токеном бота. Подделать её нельзя, так что это надёжнее любых
# самодельных токенов. CORS такой роли не выполняет: его проверяет только
# браузер, а curl и скрипты его игнорируют.


def telegram_user(
    x_telegram_init_data: Optional[str] = Header(None),
) -> Optional[dict]:
    """Проверенные данные Telegram из заголовка.

    Возвращает None, если проверка выключена (нет токена бота) — иначе
    локальная разработка и тесты стали бы невозможны.
    """
    if not config.TELEGRAM_BOT_TOKEN:
        return None
    if not x_telegram_init_data:
        raise HTTPException(status_code=401, detail="Нужен вход через Telegram")
    try:
        return telegram_auth.verify_webapp_init_data(x_telegram_init_data)
    except telegram_auth.TelegramAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


def current_profile(
    user: Optional[dict] = Depends(telegram_user),
    db: Session = Depends(get_db),
) -> Optional[models.Profile]:
    """Анкета того, кто сейчас делает запрос (None — проверка выключена)."""
    if user is None:
        return None
    return _find_profile_by_telegram(db, int(user["id"]), user.get("username"))


def _assert_is_me(actor: Optional[models.Profile], profile_id: int) -> None:
    """Запрещает действовать от чужого имени.

    actor is None — токен бота не настроен, проверка отключена.
    """
    if actor is None:
        return
    if actor.id != profile_id:
        raise HTTPException(
            status_code=403, detail="Можно действовать только от своего имени"
        )


def optional_telegram_user(
    x_telegram_init_data: Optional[str] = Header(None),
) -> Optional[dict]:
    """Как telegram_user, но молча возвращает None вместо 401.

    Нужно там, где вход необязателен: например, чтобы решить, показывать ли
    кнопку админки, но не закрывать доступ к самой странице.
    """
    if not config.TELEGRAM_BOT_TOKEN or not x_telegram_init_data:
        return None
    try:
        return telegram_auth.verify_webapp_init_data(x_telegram_init_data)
    except telegram_auth.TelegramAuthError:
        return None


def _is_admin(user: Optional[dict]) -> bool:
    if user is None:
        # Токена бота нет — подписи не проверяются, это только локальная
        # разработка. На проде токен есть всегда, иначе не работает вход.
        return not config.TELEGRAM_BOT_TOKEN
    return int(user["id"]) in config.ADMIN_TELEGRAM_IDS


def require_admin(user: Optional[dict] = Depends(optional_telegram_user)) -> None:
    """Пускает только владельцев сервиса — выгрузка содержит чужие данные."""
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Раздел только для админов")


def _assert_capacity_allowed(campus: str, capacity: int) -> None:
    """Размер комнаты должен существовать в этом кампус-отеле.

    В «Облаке» комнат на четверых нет, поэтому проверяем и здесь: фронт их
    не показывает, но запрос можно отправить и мимо него.
    """
    if not campuses.allows(campus, capacity):
        raise HTTPException(
            status_code=400,
            detail=(
                f"В кампус-отеле «{campuses.label(campus)}» комнаты только на "
                f"{campuses.capacities_text(campus)} человека"
            ),
        )


def ensure_columns() -> None:
    """Мини-миграция: добавляем новые колонки, не теряя существующие анкеты.

    Alembic не подключён, а create_all не умеет менять уже созданные таблицы.
    """
    with engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS telegram_id BIGINT")
        )
        conn.execute(
            text(
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS telegram_verified "
                "BOOLEAN NOT NULL DEFAULT FALSE"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS group_id INTEGER "
                "REFERENCES groups(id)"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS telegram_chat_id BIGINT"
            )
        )

        # Кампус-отель. Появился, когда сервис стал обслуживать два отеля.
        # DEFAULT 'disk' переселяет туда всех, кто зарегистрировался раньше:
        # тогда существовал только «Диск», в него они и записывались.
        for table in ("profiles", "groups"):
            conn.execute(
                text(
                    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS campus "
                    f"VARCHAR(20) NOT NULL DEFAULT '{campuses.DISK}'"
                )
            )

        # Возраст и курс больше не обязательны — их перестали собирать.
        conn.execute(text("ALTER TABLE profiles ALTER COLUMN age DROP NOT NULL"))

        # NULL в room_capacity = «не предпочтительно».
        conn.execute(
            text("ALTER TABLE profiles ALTER COLUMN room_capacity DROP NOT NULL")
        )

        # «О себе» — была в модели, но не в миграции: на базах, где таблица уже
        # существовала до этого поля, любой запрос к анкетам падал с ошибкой
        # "column profiles.bio does not exist".
        conn.execute(
            text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS bio TEXT NOT NULL DEFAULT ''")
        )

        # Факультет (свободный текст) → направление (5 вариантов).
        conn.execute(
            text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS track VARCHAR(20)")
        )
        has_faculty = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'profiles' AND column_name = 'faculty'"
            )
        ).first()
        if has_faculty:
            # Переносим старые факультеты по смыслу, остальное — «не определился».
            conn.execute(
                text(
                    """
                    UPDATE profiles SET track = CASE
                        WHEN faculty ILIKE '%дизайн%' THEN 'design'
                        WHEN faculty ILIKE '%информатик%'
                          OR faculty ILIKE '%математик%'
                          OR faculty ILIKE '%программ%' THEN 'dev'
                        WHEN faculty ILIKE '%эконом%'
                          OR faculty ILIKE '%бизнес%'
                          OR faculty ILIKE '%менеджмент%' THEN 'business'
                        WHEN faculty ILIKE '%искусственн%' THEN 'ai'
                        ELSE 'undecided'
                    END
                    WHERE track IS NULL
                    """
                )
            )
            conn.execute(text("ALTER TABLE profiles DROP COLUMN faculty"))
        conn.execute(
            text("UPDATE profiles SET track = 'undecided' WHERE track IS NULL")
        )
        conn.execute(text("ALTER TABLE profiles ALTER COLUMN track SET NOT NULL"))

        # Курс. NULL = «не выбран»; принудительно ставить 1-й нельзя — это
        # враньё в чужой анкете (см. блок «не выбрано» ниже).
        conn.execute(
            text("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS course INTEGER")
        )

        # Новые бытовые поля анкеты.
        for column, default in (
            ("wakeup", "alarm_one"),
            ("cooking", "self"),
            ("guests", "sometimes"),
        ):
            conn.execute(
                text(
                    f"ALTER TABLE profiles ADD COLUMN IF NOT EXISTS {column} "
                    f"VARCHAR(20) NOT NULL DEFAULT '{default}'"
                )
            )
        # Готовка теперь допускает несколько значений через запятую — нужна ширина.
        conn.execute(
            text("ALTER TABLE profiles ALTER COLUMN cooking TYPE VARCHAR(60)")
        )

        # Быт по просьбам пользователей: душ, температура, звук, алкоголь.
        for column, default in (
            ("shower", "any"),
            ("temperature", "medium"),
            ("noise", "headphones"),
            ("alcohol", "sometimes"),
        ):
            conn.execute(
                text(
                    f"ALTER TABLE profiles ADD COLUMN IF NOT EXISTS {column} "
                    f"VARCHAR(20) NOT NULL DEFAULT '{default}'"
                )
            )

        # Чистоплотность (1..5) → аккуратность (relaxed | medium | neat).
        conn.execute(
            text(
                "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS tidiness "
                "VARCHAR(20) NOT NULL DEFAULT 'medium'"
            )
        )
        has_cleanliness = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'profiles' AND column_name = 'cleanliness'"
            )
        ).first()
        if has_cleanliness:
            conn.execute(
                text(
                    """
                    UPDATE profiles SET tidiness = CASE
                        WHEN cleanliness <= 2 THEN 'relaxed'
                        WHEN cleanliness >= 4 THEN 'neat'
                        ELSE 'medium'
                    END
                    """
                )
            )
            conn.execute(text("ALTER TABLE profiles DROP COLUMN cleanliness"))

        # ===== «Не выбрано» вместо выдуманных значений =====
        # Идёт последним: к этому моменту все колонки точно существуют.
        # Курс — исключение: варианта «не выбрано» у него нет, по умолчанию 1-й.
        conn.execute(text("UPDATE profiles SET course = 1 WHERE course IS NULL"))
        conn.execute(text("ALTER TABLE profiles ALTER COLUMN course SET DEFAULT 1"))
        conn.execute(text("ALTER TABLE profiles ALTER COLUMN course SET NOT NULL"))
        # Курсов на бакалавриате всего 4, а раньше в анкете предлагались 5 и 6.
        # Без этого анкеты со старыми значениями перестали бы отдаваться:
        # схема ответа их больше не пропускает, и лента падала бы с ошибкой.
        conn.execute(text("UPDATE profiles SET course = 4 WHERE course > 4"))
        for column in (
            "track",
            "sleep_schedule",
            "smoking",
            "tidiness",
            "wakeup",
            "cooking",
            "guests",
            "shower",
            "temperature",
            "noise",
            "alcohol",
        ):
            conn.execute(
                text(f"ALTER TABLE profiles ALTER COLUMN {column} SET DEFAULT ''")
            )

        # Одноразовый сброс. Эти поля раньше проставлялись дефолтом всем подряд
        # («один будильник», «готовит сам»…), хотя человек их не выбирал — в
        # чужих анкетах появлялась неправда. Чистим ровно один раз: маркер в
        # schema_meta не даёт затереть уже осознанно заполненные анкеты.
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_meta ("
                "key VARCHAR(80) PRIMARY KEY, applied_at TIMESTAMP DEFAULT now())"
            )
        )
        already = conn.execute(
            text("SELECT 1 FROM schema_meta WHERE key = 'reset_fabricated_defaults'")
        ).first()
        if not already:
            conn.execute(
                text(
                    """
                    UPDATE profiles SET
                        wakeup = '',
                        cooking = '',
                        guests = '',
                        shower = '',
                        temperature = '',
                        noise = '',
                        alcohol = ''
                    """
                )
            )
            conn.execute(
                text(
                    "INSERT INTO schema_meta (key) "
                    "VALUES ('reset_fabricated_defaults')"
                )
            )


@app.on_event("startup")
def on_startup():
    wait_for_db()
    Base.metadata.create_all(bind=engine)
    ensure_columns()
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    # Раздаём загруженные фото. Монтируем после старта, когда папка точно есть.
    app.mount(
        storage.PUBLIC_PREFIX,
        StaticFiles(directory=config.UPLOAD_DIR),
        name="media",
    )


@app.get("/api/config", response_model=schemas.ConfigOut)
def get_config(user: Optional[dict] = Depends(optional_telegram_user)):
    """Фронтенд спрашивает, показывать ли кнопку входа через Telegram."""
    return schemas.ConfigOut(
        telegram_enabled=config.telegram_enabled(),
        telegram_bot_username=config.TELEGRAM_BOT_USERNAME or None,
        max_upload_bytes=config.MAX_UPLOAD_BYTES,
        # Кнопку админки показываем только своим. Это лишь про интерфейс —
        # сами ручки проверяют подпись отдельно (см. require_admin).
        is_admin=_is_admin(user),
    )


@app.post("/api/uploads/photo", response_model=schemas.PhotoOut, status_code=201)
async def upload_photo(file: UploadFile = File(...)):
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Пустой файл")
    if len(raw) > config.MAX_UPLOAD_BYTES:
        limit_mb = config.MAX_UPLOAD_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=413, detail=f"Файл больше {limit_mb} МБ — выбери поменьше"
        )
    try:
        url = storage.save_image(raw)
    except storage.InvalidImage as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return schemas.PhotoOut(photo_url=url)


async def _telegram_profile(user: dict) -> schemas.TelegramProfileOut:
    """Из проверенных данных Telegram делаем превью для формы.

    Аватар скачиваем себе: ссылки t.me/i/userpic/... живут недолго.
    """
    photo_url = None
    remote = user.get("photo_url")
    if remote:
        raw = await telegram_auth.download_avatar(remote)
        if raw:
            try:
                photo_url = storage.save_image(raw)
            except storage.InvalidImage:
                photo_url = None

    name = " ".join(
        part for part in [user.get("first_name"), user.get("last_name")] if part
    ).strip()
    return schemas.TelegramProfileOut(
        telegram_id=int(user["id"]),
        telegram=user.get("username"),
        name=name or None,
        photo_url=photo_url,
    )


@app.post("/api/auth/telegram", response_model=schemas.TelegramProfileOut)
async def auth_telegram(payload: schemas.TelegramWidgetAuth):
    """Вход через Telegram Login Widget (обычный веб)."""
    try:
        user = telegram_auth.verify_login_widget(payload.model_dump())
    except telegram_auth.TelegramAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    return await _telegram_profile(user)


@app.post("/api/auth/telegram/webapp", response_model=schemas.TelegramProfileOut)
async def auth_telegram_webapp(payload: schemas.TelegramWebAppAuth):
    """Вход из Telegram Mini App (сайт открыт внутри Telegram)."""
    try:
        user = telegram_auth.verify_webapp_init_data(payload.init_data)
    except telegram_auth.TelegramAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    return await _telegram_profile(user)


@app.post("/api/telegram/photos", response_model=schemas.TelegramPhotosOut)
async def telegram_photos(payload: schemas.TelegramPhotosIn):
    """Аватарки из профиля Telegram — чтобы человек выбрал нужную.

    Раньше молча бралась первая, хотя у многих аватарок несколько.
    Отдаём порциями: total подскажет фронту, осталось ли что догружать.
    """
    try:
        user = telegram_auth.verify_webapp_init_data(payload.init_data)
    except telegram_auth.TelegramAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    blobs, total = await telegram_auth.fetch_profile_photos(
        int(user["id"]), limit=payload.limit, offset=payload.offset
    )
    urls: List[str] = []
    for blob in blobs:
        try:
            urls.append(storage.save_image(blob))
        except storage.InvalidImage:
            continue
    return schemas.TelegramPhotosOut(photos=urls, total=total)


@app.get(
    "/api/profiles",
    response_model=List[schemas.ProfileOut],
    dependencies=[Depends(telegram_user)],
)
def list_profiles(
    db: Session = Depends(get_db),
    gender: Optional[str] = Query(None, pattern="^(male|female|other)$"),
    campus: Optional[str] = Query(None, pattern=campuses.PATTERN),
    room_capacity: Optional[int] = Query(None, ge=2, le=4),
    smoking: Optional[str] = Query(None, pattern=schemas.SMOKING_PATTERN),
    sleep_schedule: Optional[str] = Query(None, pattern="^(lark|owl|any)$"),
    track: Optional[str] = Query(None, pattern=schemas.TRACK_PATTERN),
    course: Optional[int] = Query(None, ge=1, le=4),
    tidiness: Optional[str] = Query(None, pattern=schemas.TIDINESS_PATTERN),
    wakeup: Optional[str] = Query(None, pattern=schemas.WAKEUP_PATTERN),
    cooking: Optional[str] = Query(None, pattern=schemas.COOKING_ITEM_PATTERN),
    guests: Optional[str] = Query(None, pattern=schemas.GUESTS_PATTERN),
    shower: Optional[str] = Query(None, pattern=schemas.SHOWER_PATTERN),
    temperature: Optional[str] = Query(None, pattern=schemas.TEMPERATURE_PATTERN),
    noise: Optional[str] = Query(None, pattern=schemas.NOISE_PATTERN),
    alcohol: Optional[str] = Query(None, pattern=schemas.ALCOHOL_PATTERN),
    search: Optional[str] = Query(None),
    without_group: Optional[bool] = Query(
        None, description="true — только те, кто ещё не в компании"
    ),
):
    query = db.query(models.Profile)
    if gender:
        query = query.filter(models.Profile.gender == gender)
    if campus:
        query = query.filter(models.Profile.campus == campus)
    if without_group is True:
        query = query.filter(models.Profile.group_id.is_(None))
    elif without_group is False:
        query = query.filter(models.Profile.group_id.isnot(None))
    if room_capacity:
        # Кому «не предпочтительно» (NULL) — подходит любой размер, поэтому
        # такие анкеты показываем и при фильтре по конкретному числу.
        query = query.filter(
            (models.Profile.room_capacity == room_capacity)
            | (models.Profile.room_capacity.is_(None))
        )
    if smoking:
        query = query.filter(models.Profile.smoking == smoking)
    if sleep_schedule:
        query = query.filter(models.Profile.sleep_schedule == sleep_schedule)
    if track:
        query = query.filter(models.Profile.track == track)
    if course:
        query = query.filter(models.Profile.course == course)
    if tidiness:
        query = query.filter(models.Profile.tidiness == tidiness)
    if wakeup:
        query = query.filter(models.Profile.wakeup == wakeup)
    if guests:
        query = query.filter(models.Profile.guests == guests)
    if shower:
        query = query.filter(models.Profile.shower == shower)
    if temperature:
        query = query.filter(models.Profile.temperature == temperature)
    if noise:
        query = query.filter(models.Profile.noise == noise)
    if alcohol:
        query = query.filter(models.Profile.alcohol == alcohol)
    if cooking:
        # cooking хранится списком через запятую ("self,together"). Обрамляем
        # запятыми с обеих сторон, чтобы искать элемент целиком, а не подстроку.
        query = query.filter(
            func.concat(",", models.Profile.cooking, ",").like(f"%,{cooking},%")
        )
    if search:
        # Направление теперь выбирается фильтром, а не ищется текстом.
        like = f"%{search.lower()}%"
        query = query.filter(
            (models.Profile.name.ilike(like)) | (models.Profile.bio.ilike(like))
        )
    return query.order_by(models.Profile.created_at.desc()).all()


@app.post("/api/profiles/me", response_model=schemas.ProfileOut)
def resolve_my_profile(
    payload: schemas.TelegramWebAppAuth, db: Session = Depends(get_db)
):
    """«Кто я» по подписи Telegram.

    Мини-апп зовёт это при старте: localStorage может быть пуст (другое
    устройство, очистка кэша), а анкета при этом уже есть — раньше в такой
    ситуации предлагалось создать вторую.
    """
    try:
        user = telegram_auth.verify_webapp_init_data(payload.init_data)
    except telegram_auth.TelegramAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    profile = _find_profile_by_telegram(db, int(user["id"]), user.get("username"))
    if not profile:
        raise HTTPException(status_code=404, detail="Анкета не найдена")

    # Анкету могли создать до входа через Telegram — привязываем id сейчас,
    # чтобы дальше находить её даже при смене ника.
    if not profile.telegram_id:
        profile.telegram_id = int(user["id"])
        db.commit()
        db.refresh(profile)
    return profile


@app.get(
    "/api/profiles/{profile_id}",
    response_model=schemas.ProfileOut,
    dependencies=[Depends(telegram_user)],
)
def get_profile(profile_id: int, db: Session = Depends(get_db)):
    profile = db.query(models.Profile).filter(models.Profile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль не найден")
    return profile


@app.post("/api/profiles", response_model=schemas.ProfileOut, status_code=201)
def create_profile(payload: schemas.ProfileCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    widget_auth = data.pop("telegram_auth", None)
    init_data = data.pop("telegram_init_data", None)

    data["telegram"] = payload.telegram.lstrip("@").strip()
    data["telegram_id"] = None
    data["telegram_verified"] = False

    # Флаг «подтверждено» ставим только сами, после повторной проверки подписи.
    verified_user = None
    try:
        if widget_auth:
            verified_user = telegram_auth.verify_login_widget(widget_auth)
        elif init_data:
            verified_user = telegram_auth.verify_webapp_init_data(init_data)
    except telegram_auth.TelegramAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    if verified_user:
        data["telegram_id"] = int(verified_user["id"])
        data["telegram_verified"] = True
        # Ник берём из подтверждённых данных, чтобы нельзя было указать чужой.
        if verified_user.get("username"):
            data["telegram"] = str(verified_user["username"]).lstrip("@")

    # Предпочтение по размеру комнаты должно существовать в выбранном кампус-отеле.
    if data.get("room_capacity"):
        _assert_capacity_allowed(data["campus"], data["room_capacity"])

    # Готовка приходит списком, а в колонке лежит строкой через запятую.
    data["cooking"] = ",".join(data["cooking"])

    profile = models.Profile(**data)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@app.put("/api/profiles/{profile_id}", response_model=schemas.ProfileOut)
def update_profile(
    profile_id: int,
    payload: schemas.ProfileUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    actor: Optional[models.Profile] = Depends(current_profile),
):
    """Редактирование своей анкеты.

    Полноценной авторизации нет: правит тот, у кого в браузере сохранён id.
    Пол не трогаем (он влияет на подбор компании), а подтверждённый через
    Telegram ник менять нельзя — иначе подтверждение потеряет смысл.

    Кампус-отель сменить можно, но это переезд: в чужом отеле и комната, и заявки,
    и приглашения теряют смысл, поэтому они закрываются.
    """
    _assert_is_me(actor, profile_id)
    profile = _get_profile_or_404(db, profile_id)
    data = payload.model_dump()

    # Пол задаётся один раз при создании и дальше не меняется.
    data.pop("gender", None)
    if profile.telegram_verified:
        data.pop("telegram", None)
    else:
        data["telegram"] = payload.telegram.lstrip("@").strip()

    if data.get("room_capacity"):
        _assert_capacity_allowed(data["campus"], data["room_capacity"])

    msgs: List[dict] = []
    if data["campus"] != profile.campus:
        msgs = _remove_from_group(
            db, profile, note="переехал(а) в другой кампус-отель и вышел(а) из комнаты"
        )
        _close_pending(db, profile)

    # Готовка — список значений, храним строкой через запятую.
    data["cooking"] = ",".join(data["cooking"])

    for key, value in data.items():
        setattr(profile, key, value)
    db.commit()
    db.refresh(profile)

    background_tasks.add_task(notifier.deliver, msgs)
    return profile


@app.delete("/api/profiles/{profile_id}", status_code=204)
def delete_profile(
    profile_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    actor: Optional[models.Profile] = Depends(current_profile),
):
    """Удаление своей анкеты: заодно выводим из компании и чистим заявки."""
    _assert_is_me(actor, profile_id)
    profile = _get_profile_or_404(db, profile_id)

    # Сообщения собираем ДО удаления, пока объекты ещё в сессии.
    msgs = _remove_from_group(
        db, profile, note="удалил(а) анкету и вышел(а) из комнаты"
    )
    _close_pending(db, profile)

    db.delete(profile)
    db.commit()

    background_tasks.add_task(notifier.deliver, msgs)
    return None


def _get_profile_or_404(db: Session, profile_id: int) -> models.Profile:
    profile = db.query(models.Profile).filter(models.Profile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Анкета не найдена")
    return profile


def _get_group_or_404(db: Session, group_id: int) -> models.Group:
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    return group


def _get_request_or_404(db: Session, request_id: int) -> models.JoinRequest:
    req = (
        db.query(models.JoinRequest)
        .filter(models.JoinRequest.id == request_id)
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    return req


TRACK_LABEL = {
    "dev": "Разработка",
    "business": "Бизнес",
    "design": "Дизайн",
    "ai": "ИИ",
    "undecided": "Не определился",
}


def _who(profile: models.Profile) -> str:
    label = TRACK_LABEL.get(profile.track)
    return f"{profile.name} · {label}" if label else profile.name


def _msg(chat_id: Optional[int], text: str, reply_markup: Optional[dict] = None):
    """Один пункт для фоновой рассылки; без chat_id (не нажали /start) — пропуск."""
    return {"chat_id": chat_id, "text": text, "reply_markup": reply_markup}


def _request_msgs(req: models.JoinRequest) -> List[dict]:
    """Заявка ушла — зовём подтвердить всех, кто в комнате."""
    who = _who(req.profile)
    needed = join_flow.votes_needed(req)
    msgs = []
    for member in req.group.members:
        if member.telegram_chat_id:
            msgs.append(
                _msg(
                    member.telegram_chat_id,
                    f"🔔 <b>{who}</b> просится к вам в комнату на {req.group.capacity}.\n"
                    f"@{req.profile.telegram}\n\n"
                    f"Нужно согласие всех участников ({needed}).",
                    notifier.vote_keyboard(req.id),
                )
            )
    return msgs


def _decision_msgs(req: models.JoinRequest, status: str) -> List[dict]:
    """Сообщаем автору заявки итог (приняли / отклонили / компания распалась)."""
    profile = req.profile
    if not profile.telegram_chat_id:
        return []
    if status == join_flow.APPROVED:
        mates = ", ".join(m.name for m in req.group.members if m.id != profile.id)
        return [
            _msg(
                profile.telegram_chat_id,
                f"🎉 Тебя приняли в комнату на {req.group.capacity}!\n"
                f"Соседи: {mates or '—'}\n\n{config.SITE_URL}",
            )
        ]
    if status == join_flow.REJECTED:
        return [
            _msg(
                profile.telegram_chat_id,
                "😔 Заявку в комнату отклонили. Не расстраивайся — "
                f"есть другие варианты: {config.SITE_URL}",
            )
        ]
    if status == join_flow.CANCELLED:
        return [
            _msg(profile.telegram_chat_id, "ℹ️ Заявка отменена: компания распалась.")
        ]
    return []


def _remove_from_group(
    db: Session,
    profile: models.Profile,
    note: str = "вышел(а) из вашей комнаты",
) -> List[dict]:
    """Выводит человека из комнаты и собирает уведомления оставшимся.

    Сообщения не шлёт, а возвращает: вызывающий отправит их в фоне уже после
    ответа клиенту. Опустевшую комнату удаляем — она никому не нужна.
    Одна дорога на все случаи выхода: вышел сам, удалил анкету, переехал.
    """
    group = profile.group if profile.group_id else None
    if group is None:
        return []

    left_name = profile.name
    profile.group_id = None
    db.flush()
    db.refresh(group)

    # Состав изменился — часть заявок могла «дозреть» без ушедшего.
    decided = []
    for req in list(group.requests):
        if req.status == join_flow.PENDING:
            new_status = join_flow.evaluate(db, req)
            if new_status != join_flow.PENDING:
                decided.append((req, new_status))

    msgs: List[dict] = []
    for member in group.members:
        if member.telegram_chat_id:
            msgs.append(
                _msg(
                    member.telegram_chat_id,
                    f"🚪 <b>{left_name}</b> {note}.\n"
                    f"Свободных мест стало больше: {config.SITE_URL}",
                )
            )
    for req, status in decided:
        msgs += _decision_msgs(req, status)

    if not group.members:
        db.delete(group)
    return msgs


def _close_pending(db: Session, profile: models.Profile) -> None:
    """Закрывает исходящие заявки и приглашения человека.

    Нужно, когда он выбывает: удалил анкету или переехал в другой кампус-отель —
    висящие «ждём ответа» после этого только путают остальных.
    """
    now = datetime.utcnow()
    db.query(models.JoinRequest).filter(
        models.JoinRequest.profile_id == profile.id,
        models.JoinRequest.status == join_flow.PENDING,
    ).update({"status": join_flow.CANCELLED, "decided_at": now})
    db.query(models.GroupInvite).filter(
        models.GroupInvite.status == "pending",
        (models.GroupInvite.from_profile_id == profile.id)
        | (models.GroupInvite.to_profile_id == profile.id),
    ).update({"status": "cancelled", "decided_at": now})


def _apply_vote(
    db: Session, req: models.JoinRequest, voter: models.Profile, approve: bool
) -> tuple[str, List[dict]]:
    """Записывает голос, пересчитывает статус и СОБИРАЕТ уведомления.

    Сами сообщения не шлёт — возвращает их, чтобы вызывающий отправил в фоне
    (BackgroundTasks) уже после ответа клиенту.
    """
    vote = (
        db.query(models.JoinRequestVote)
        .filter(
            models.JoinRequestVote.request_id == req.id,
            models.JoinRequestVote.member_id == voter.id,
        )
        .first()
    )
    if vote:
        vote.approve = approve  # передумал — перезаписываем
    else:
        db.add(
            models.JoinRequestVote(
                request_id=req.id, member_id=voter.id, approve=approve
            )
        )
    db.flush()
    db.refresh(req)

    status = join_flow.evaluate(db, req)
    also_rejected = []
    if status == join_flow.APPROVED:
        also_rejected = join_flow.close_obsolete(db, req.profile, req.group)
    db.commit()
    db.refresh(req)

    msgs: List[dict] = []
    if status != join_flow.PENDING:
        msgs += _decision_msgs(req, status)
    if status == join_flow.APPROVED:
        # Остальным в комнате — что состав пополнился.
        for member in req.group.members:
            if member.id != req.profile_id and member.telegram_chat_id:
                msgs.append(
                    _msg(
                        member.telegram_chat_id,
                        f"✅ <b>{req.profile.name}</b> теперь в вашей комнате.",
                    )
                )
        for other in also_rejected:
            msgs += _decision_msgs(other, join_flow.REJECTED)
    return status, msgs


@app.get(
    "/api/groups",
    response_model=List[schemas.GroupOut],
    dependencies=[Depends(telegram_user)],
)
def list_groups(
    db: Session = Depends(get_db),
    gender: Optional[str] = Query(None, pattern="^(male|female|other)$"),
    campus: Optional[str] = Query(None, pattern=campuses.PATTERN),
    only_open: Optional[bool] = Query(None, description="true — только с местами"),
):
    query = db.query(models.Group)
    if gender:
        query = query.filter(models.Group.gender == gender)
    if campus:
        query = query.filter(models.Group.campus == campus)
    groups = query.order_by(models.Group.created_at.desc()).all()
    if only_open:
        groups = [g for g in groups if g.spots_left > 0]
    return groups


@app.get(
    "/api/groups/{group_id}",
    response_model=schemas.GroupOut,
    dependencies=[Depends(telegram_user)],
)
def get_group(group_id: int, db: Session = Depends(get_db)):
    return _get_group_or_404(db, group_id)


@app.post("/api/groups", response_model=schemas.GroupOut, status_code=201)
def create_group(
    payload: schemas.GroupCreate,
    db: Session = Depends(get_db),
    actor: Optional[models.Profile] = Depends(current_profile),
):
    """Создаёт компанию: автор сразу становится первым участником."""
    _assert_is_me(actor, payload.profile_id)
    profile = _get_profile_or_404(db, payload.profile_id)
    if profile.group_id:
        raise HTTPException(status_code=409, detail="Ты уже состоишь в компании")
    _assert_capacity_allowed(profile.campus, payload.capacity)

    group = models.Group(
        capacity=payload.capacity, gender=profile.gender, campus=profile.campus
    )
    db.add(group)
    db.flush()  # нужен id до привязки участника
    profile.group_id = group.id
    db.commit()
    db.refresh(group)
    return group


def _request_out(req: models.JoinRequest) -> schemas.JoinRequestOut:
    votes = join_flow.active_votes(req)
    return schemas.JoinRequestOut(
        id=req.id,
        group_id=req.group_id,
        status=req.status,
        created_at=req.created_at,
        profile=schemas.GroupMemberOut.model_validate(req.profile),
        votes_needed=join_flow.votes_needed(req),
        votes_done=join_flow.votes_done(req),
        approved_by=[mid for mid, ok in votes.items() if ok],
    )


@app.get("/api/groups/{group_id}/requests", response_model=List[schemas.JoinRequestOut])
def list_group_requests(
    group_id: int,
    db: Session = Depends(get_db),
    status: Optional[str] = Query("pending"),
    actor: Optional[models.Profile] = Depends(current_profile),
):
    group = _get_group_or_404(db, group_id)
    # Заявки — внутреннее дело комнаты: чужим их видеть незачем.
    if actor is not None and actor.group_id != group.id:
        raise HTTPException(status_code=403, detail="Это не твоя комната")
    reqs = [r for r in group.requests if not status or r.status == status]
    reqs.sort(key=lambda r: r.created_at)
    return [_request_out(r) for r in reqs]


@app.get(
    "/api/profiles/{profile_id}/requests", response_model=List[schemas.JoinRequestOut]
)
def list_my_requests(
    profile_id: int,
    db: Session = Depends(get_db),
    status: Optional[str] = Query("pending"),
    actor: Optional[models.Profile] = Depends(current_profile),
):
    _assert_is_me(actor, profile_id)
    _get_profile_or_404(db, profile_id)
    query = db.query(models.JoinRequest).filter(
        models.JoinRequest.profile_id == profile_id
    )
    if status:
        query = query.filter(models.JoinRequest.status == status)
    return [_request_out(r) for r in query.all()]


@app.post(
    "/api/groups/{group_id}/requests",
    response_model=schemas.JoinRequestOut,
    status_code=201,
)
def create_join_request(
    group_id: int,
    payload: schemas.JoinRequestCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    actor: Optional[models.Profile] = Depends(current_profile),
):
    """Заявка на вступление. Сама по себе в комнату не пускает."""
    _assert_is_me(actor, payload.profile_id)
    group = _get_group_or_404(db, group_id)
    profile = _get_profile_or_404(db, payload.profile_id)

    if profile.group_id == group.id:
        raise HTTPException(status_code=409, detail="Ты уже в этой компании")
    if profile.group_id:
        raise HTTPException(status_code=409, detail="Сначала выйди из текущей компании")
    if profile.gender != group.gender:
        raise HTTPException(
            status_code=403, detail="Парни живут с парнями, девушки — с девушками"
        )
    if profile.campus != group.campus:
        raise HTTPException(
            status_code=403,
            detail=f"Эта комната в кампус-отеле «{campuses.label(group.campus)}»",
        )
    if group.spots_left <= 0:
        raise HTTPException(status_code=409, detail="В компании больше нет мест")

    existing = (
        db.query(models.JoinRequest)
        .filter(
            models.JoinRequest.group_id == group.id,
            models.JoinRequest.profile_id == profile.id,
            models.JoinRequest.status == join_flow.PENDING,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Заявка уже отправлена")

    req = models.JoinRequest(group_id=group.id, profile_id=profile.id)
    db.add(req)
    db.commit()
    db.refresh(req)

    background_tasks.add_task(notifier.deliver, _request_msgs(req))
    return _request_out(req)


@app.post("/api/requests/{request_id}/vote", response_model=schemas.JoinRequestOut)
def vote_request(
    request_id: int,
    payload: schemas.JoinRequestVoteIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    actor: Optional[models.Profile] = Depends(current_profile),
):
    _assert_is_me(actor, payload.profile_id)
    req = _get_request_or_404(db, request_id)
    voter = _get_profile_or_404(db, payload.profile_id)

    if req.status != join_flow.PENDING:
        raise HTTPException(status_code=409, detail="Заявка уже закрыта")
    if voter.group_id != req.group_id:
        raise HTTPException(
            status_code=403, detail="Голосовать могут только те, кто в комнате"
        )

    _status, msgs = _apply_vote(db, req, voter, payload.approve)
    background_tasks.add_task(notifier.deliver, msgs)
    db.refresh(req)
    return _request_out(req)


@app.post("/api/requests/{request_id}/cancel", status_code=204)
def cancel_request(
    request_id: int,
    payload: schemas.GroupMembership,
    db: Session = Depends(get_db),
    actor: Optional[models.Profile] = Depends(current_profile),
):
    _assert_is_me(actor, payload.profile_id)
    req = _get_request_or_404(db, request_id)
    if req.profile_id != payload.profile_id:
        raise HTTPException(status_code=403, detail="Это не твоя заявка")
    if req.status != join_flow.PENDING:
        raise HTTPException(status_code=409, detail="Заявка уже закрыта")
    req.status = join_flow.CANCELLED
    req.decided_at = datetime.utcnow()
    db.commit()
    return None


@app.post("/api/groups/{group_id}/leave", status_code=204)
def leave_group(
    group_id: int,
    payload: schemas.GroupMembership,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    actor: Optional[models.Profile] = Depends(current_profile),
):
    _assert_is_me(actor, payload.profile_id)
    group = _get_group_or_404(db, group_id)
    profile = _get_profile_or_404(db, payload.profile_id)
    if profile.group_id != group.id:
        raise HTTPException(status_code=409, detail="Ты не состоишь в этой компании")

    # Сообщения собираем до коммита, пока объекты в сессии.
    msgs = _remove_from_group(db, profile)
    db.commit()

    background_tasks.add_task(notifier.deliver, msgs)
    return None


@app.post("/api/groups/{group_id}/capacity", response_model=schemas.GroupOut)
def change_group_capacity(
    group_id: int,
    payload: schemas.GroupCapacityIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    actor: Optional[models.Profile] = Depends(current_profile),
):
    """Сузить или расширить уже созданную комнату.

    Собрались вчетвером, а набралось двое — не нужно распускать компанию и
    собирать заново: комнату на 4 можно сделать комнатой на 2. Меняет любой
    жилец, остальные узнают об этом из Telegram.
    """
    _assert_is_me(actor, payload.profile_id)
    group = _get_group_or_404(db, group_id)
    profile = _get_profile_or_404(db, payload.profile_id)

    if profile.group_id != group.id:
        raise HTTPException(
            status_code=403, detail="Размер комнаты меняют только те, кто в ней живёт"
        )
    _assert_capacity_allowed(group.campus, payload.capacity)

    taken = len(group.members)
    if payload.capacity < taken:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Вас уже {taken} — комната на {payload.capacity} не вместит. "
                "Сначала кто-то должен выйти"
            ),
        )
    if payload.capacity == group.capacity:
        return group

    was = group.capacity
    group.capacity = payload.capacity
    db.flush()
    db.refresh(group)

    # Комнату могли ужать «под ноль» — тогда ждущие заявки теряют смысл.
    rejected: List[models.JoinRequest] = []
    if group.spots_left <= 0:
        for req in list(group.requests):
            if req.status == join_flow.PENDING:
                req.status = join_flow.REJECTED
                req.decided_at = datetime.utcnow()
                rejected.append(req)

    msgs: List[dict] = []
    for member in group.members:
        if member.id != profile.id and member.telegram_chat_id:
            msgs.append(
                _msg(
                    member.telegram_chat_id,
                    f"🔁 <b>{profile.name}</b> изменил(а) размер вашей комнаты: "
                    f"была на {was}, стала на {payload.capacity}.\n"
                    f"{config.SITE_URL}",
                )
            )
    for req in rejected:
        if req.profile.telegram_chat_id:
            msgs.append(
                _msg(
                    req.profile.telegram_chat_id,
                    "😔 Комнату сделали меньше, и мест в ней не осталось — "
                    f"твоя заявка закрыта. Есть другие варианты: {config.SITE_URL}",
                )
            )

    db.commit()
    db.refresh(group)

    background_tasks.add_task(notifier.deliver, msgs)
    return group


# ===== Приглашения «давай жить вместе» =====


def _get_invite_or_404(db: Session, invite_id: int) -> models.GroupInvite:
    invite = (
        db.query(models.GroupInvite)
        .filter(models.GroupInvite.id == invite_id)
        .first()
    )
    if not invite:
        raise HTTPException(status_code=404, detail="Приглашение не найдено")
    return invite


def _assert_invite_still_valid(invite: models.GroupInvite) -> None:
    """Между приглашением и согласием могло многое измениться.

    Пока человек думал, любой из двоих мог вступить в другую компанию или
    переехать в другой кампус-отель — тогда комнату создавать уже нельзя.
    """
    if invite.from_profile.group_id or invite.to_profile.group_id:
        raise HTTPException(
            status_code=409, detail="Кто-то из вас уже успел вступить в компанию"
        )
    if invite.from_profile.campus != invite.to_profile.campus:
        raise HTTPException(
            status_code=409,
            detail="Кто-то из вас сменил кампус-отель — приглашение больше не действует",
        )
    _assert_capacity_allowed(invite.from_profile.campus, invite.capacity)


def _invite_msgs(invite: models.GroupInvite) -> List[dict]:
    """Зовём приглашённого подтвердить — кнопками прямо в Telegram."""
    target = invite.to_profile
    if not target.telegram_chat_id:
        return []
    return [
        _msg(
            target.telegram_chat_id,
            f"🤝 <b>{_who(invite.from_profile)}</b> зовёт тебя жить вместе — "
            f"комната на {invite.capacity}.\n"
            f"@{invite.from_profile.telegram}\n\n"
            "Комната появится, только если ты согласишься.",
            notifier.invite_keyboard(invite.id),
        )
    ]


def _accept_invite(
    db: Session, invite: models.GroupInvite
) -> tuple[models.Group, List[dict]]:
    """Согласие: создаём комнату и заводим туда обоих."""
    author, target = invite.from_profile, invite.to_profile

    group = models.Group(
        capacity=invite.capacity, gender=author.gender, campus=author.campus
    )
    db.add(group)
    db.flush()  # нужен id до привязки участников
    author.group_id = group.id
    target.group_id = group.id

    invite.status = "accepted"
    invite.decided_at = datetime.utcnow()

    # Оба определились — их прочие заявки и приглашения теряют смысл.
    for profile in (author, target):
        db.query(models.JoinRequest).filter(
            models.JoinRequest.profile_id == profile.id,
            models.JoinRequest.status == join_flow.PENDING,
        ).update({"status": join_flow.CANCELLED, "decided_at": datetime.utcnow()})
        db.query(models.GroupInvite).filter(
            models.GroupInvite.id != invite.id,
            models.GroupInvite.status == "pending",
            (models.GroupInvite.from_profile_id == profile.id)
            | (models.GroupInvite.to_profile_id == profile.id),
        ).update({"status": "cancelled", "decided_at": datetime.utcnow()})

    msgs: List[dict] = []
    if author.telegram_chat_id:
        msgs.append(
            _msg(
                author.telegram_chat_id,
                f"🎉 <b>{target.name}</b> согласи(лся/лась) жить с тобой!\n"
                f"Комната на {invite.capacity} создана: {config.SITE_URL}",
            )
        )
    db.commit()
    db.refresh(group)
    return group, msgs


def _decline_invite(db: Session, invite: models.GroupInvite) -> List[dict]:
    invite.status = "declined"
    invite.decided_at = datetime.utcnow()
    author = invite.from_profile
    msgs: List[dict] = []
    if author.telegram_chat_id:
        msgs.append(
            _msg(
                author.telegram_chat_id,
                f"😔 <b>{invite.to_profile.name}</b> отказал(а)ся жить вместе. "
                f"Есть и другие варианты: {config.SITE_URL}",
            )
        )
    db.commit()
    return msgs


@app.post("/api/invites", response_model=schemas.GroupInviteOut, status_code=201)
def create_invite(
    payload: schemas.GroupInviteCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    actor: Optional[models.Profile] = Depends(current_profile),
):
    """Позвать человека жить вместе. Комната создастся только после согласия."""
    _assert_is_me(actor, payload.from_profile_id)
    author = _get_profile_or_404(db, payload.from_profile_id)
    target = _get_profile_or_404(db, payload.to_profile_id)

    if author.id == target.id:
        raise HTTPException(status_code=400, detail="Нельзя позвать самого себя")
    if author.gender != target.gender:
        raise HTTPException(
            status_code=403, detail="Парни живут с парнями, девушки — с девушками"
        )
    if author.campus != target.campus:
        raise HTTPException(status_code=403, detail="Вы живёте в разных кампус-отелях")
    _assert_capacity_allowed(author.campus, payload.capacity)
    if author.group_id:
        raise HTTPException(status_code=409, detail="Ты уже состоишь в компании")
    if target.group_id:
        raise HTTPException(status_code=409, detail="Человек уже в компании")

    existing = (
        db.query(models.GroupInvite)
        .filter(
            models.GroupInvite.from_profile_id == author.id,
            models.GroupInvite.to_profile_id == target.id,
            models.GroupInvite.status == "pending",
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Приглашение уже отправлено")

    invite = models.GroupInvite(
        from_profile_id=author.id,
        to_profile_id=target.id,
        capacity=payload.capacity,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    background_tasks.add_task(notifier.deliver, _invite_msgs(invite))
    return invite


@app.get("/api/profiles/{profile_id}/invites", response_model=List[schemas.GroupInviteOut])
def list_my_invites(
    profile_id: int,
    db: Session = Depends(get_db),
    status: Optional[str] = Query("pending"),
    actor: Optional[models.Profile] = Depends(current_profile),
):
    """Приглашения, где человек участвует — и как звавший, и как позванный."""
    _assert_is_me(actor, profile_id)
    _get_profile_or_404(db, profile_id)
    query = db.query(models.GroupInvite).filter(
        (models.GroupInvite.from_profile_id == profile_id)
        | (models.GroupInvite.to_profile_id == profile_id)
    )
    if status:
        query = query.filter(models.GroupInvite.status == status)
    return query.order_by(models.GroupInvite.created_at.desc()).all()


@app.post("/api/invites/{invite_id}/respond", response_model=schemas.GroupInviteOut)
def respond_invite(
    invite_id: int,
    payload: schemas.GroupInviteRespond,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    actor: Optional[models.Profile] = Depends(current_profile),
):
    _assert_is_me(actor, payload.profile_id)
    invite = _get_invite_or_404(db, invite_id)
    if invite.status != "pending":
        raise HTTPException(status_code=409, detail="Приглашение уже закрыто")
    if invite.to_profile_id != payload.profile_id:
        raise HTTPException(status_code=403, detail="Это приглашение не тебе")

    if payload.accept:
        _assert_invite_still_valid(invite)
        _group, msgs = _accept_invite(db, invite)
    else:
        msgs = _decline_invite(db, invite)

    background_tasks.add_task(notifier.deliver, msgs)
    db.refresh(invite)
    return invite


@app.post("/api/invites/{invite_id}/cancel", status_code=204)
def cancel_invite(
    invite_id: int,
    payload: schemas.GroupMembership,
    db: Session = Depends(get_db),
    actor: Optional[models.Profile] = Depends(current_profile),
):
    _assert_is_me(actor, payload.profile_id)
    invite = _get_invite_or_404(db, invite_id)
    if invite.from_profile_id != payload.profile_id:
        raise HTTPException(status_code=403, detail="Это не твоё приглашение")
    if invite.status != "pending":
        raise HTTPException(status_code=409, detail="Приглашение уже закрыто")
    invite.status = "cancelled"
    invite.decided_at = datetime.utcnow()
    db.commit()
    return None


# ===== Служебные ручки для бота =====
# Бот действует от имени Telegram-пользователя, поэтому доступ только по
# общему секрету: иначе кто угодно смог бы голосовать за других.


def _check_bot_secret(x_bot_secret: Optional[str] = Header(None)) -> None:
    if not config.BOT_SECRET:
        raise HTTPException(status_code=503, detail="BOT_SECRET не настроен")
    if x_bot_secret != config.BOT_SECRET:
        raise HTTPException(status_code=401, detail="Неверный секрет бота")


def _find_profile_by_telegram(
    db: Session, telegram_id: int, username: Optional[str]
) -> Optional[models.Profile]:
    """Ищем анкету: сначала по подтверждённому telegram_id, потом по нику."""
    profile = (
        db.query(models.Profile)
        .filter(models.Profile.telegram_id == telegram_id)
        .first()
    )
    if profile:
        return profile
    if username:
        return (
            db.query(models.Profile)
            .filter(models.Profile.telegram.ilike(username.lstrip("@")))
            .first()
        )
    return None


@app.post("/api/bot/link", dependencies=[Depends(_check_bot_secret)])
def bot_link(payload: schemas.BotLink, db: Session = Depends(get_db)):
    """/start у бота: запоминаем chat_id, чтобы было куда слать уведомления."""
    profile = _find_profile_by_telegram(db, payload.telegram_id, payload.username)
    if not profile:
        return {"linked": False, "profile": None}

    profile.telegram_chat_id = payload.chat_id
    if not profile.telegram_id:
        profile.telegram_id = payload.telegram_id
    db.commit()
    db.refresh(profile)
    return {
        "linked": True,
        "profile": {
            "id": profile.id,
            "name": profile.name,
            "group_id": profile.group_id,
            # Готовую подпись отдаём с бэкенда: у бота своего справочника
            # кампус-отелей нет, и заводить второй смысла не имеет.
            "campus": campuses.label(profile.campus),
        },
    }


@app.get("/api/bot/pending", dependencies=[Depends(_check_bot_secret)])
def bot_pending(telegram_id: int, db: Session = Depends(get_db)):
    """Заявки, ждущие голоса этого человека."""
    profile = _find_profile_by_telegram(db, telegram_id, None)
    if not profile or not profile.group_id:
        return {"requests": []}
    reqs = (
        db.query(models.JoinRequest)
        .filter(
            models.JoinRequest.group_id == profile.group_id,
            models.JoinRequest.status == join_flow.PENDING,
        )
        .all()
    )
    voted = {
        v.request_id
        for v in db.query(models.JoinRequestVote).filter(
            models.JoinRequestVote.member_id == profile.id
        )
    }
    return {
        "requests": [
            {
                "id": r.id,
                "who": _who(r.profile),
                "telegram": r.profile.telegram,
                "capacity": r.group.capacity,
            }
            for r in reqs
            if r.id not in voted
        ]
    }


@app.post("/api/bot/vote", dependencies=[Depends(_check_bot_secret)])
def bot_vote(
    payload: schemas.BotVote,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Голос кнопкой в боте."""
    profile = _find_profile_by_telegram(db, payload.telegram_id, None)
    if not profile:
        raise HTTPException(status_code=404, detail="Анкета не найдена")

    req = _get_request_or_404(db, payload.request_id)
    if req.status != join_flow.PENDING:
        raise HTTPException(status_code=409, detail="Заявка уже закрыта")
    if profile.group_id != req.group_id:
        raise HTTPException(
            status_code=403, detail="Голосовать могут только те, кто в комнате"
        )

    status, msgs = _apply_vote(db, req, profile, payload.approve)
    background_tasks.add_task(notifier.deliver, msgs)
    db.refresh(req)
    return {
        "status": status,
        "votes_done": join_flow.votes_done(req),
        "votes_needed": join_flow.votes_needed(req),
        "who": req.profile.name,
    }


@app.post("/api/bot/invite", dependencies=[Depends(_check_bot_secret)])
def bot_invite_respond(
    payload: schemas.BotInviteRespond,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Ответ на приглашение «давай жить вместе» кнопкой в боте."""
    profile = _find_profile_by_telegram(db, payload.telegram_id, None)
    if not profile:
        raise HTTPException(status_code=404, detail="Анкета не найдена")

    invite = _get_invite_or_404(db, payload.invite_id)
    if invite.status != "pending":
        raise HTTPException(status_code=409, detail="Приглашение уже закрыто")
    if invite.to_profile_id != profile.id:
        raise HTTPException(status_code=403, detail="Это приглашение не тебе")

    if payload.accept:
        _assert_invite_still_valid(invite)
        _group, msgs = _accept_invite(db, invite)
        result = "accepted"
    else:
        msgs = _decline_invite(db, invite)
        result = "declined"

    background_tasks.add_task(notifier.deliver, msgs)
    return {
        "status": result,
        "capacity": invite.capacity,
        "who": invite.from_profile.name,
    }


# ===== Админка =====
# Выгрузка чужих персональных данных, поэтому за require_admin: подпись
# Telegram должна принадлежать одному из владельцев сервиса.


@app.get(
    "/api/admin/stats",
    response_model=schemas.AdminStatsOut,
    dependencies=[Depends(require_admin)],
)
def admin_stats(db: Session = Depends(get_db)):
    """Сводка перед выгрузкой: сколько всего и сколько с кем можно связаться."""
    profiles = db.query(models.Profile).all()
    groups = db.query(models.Group).all()

    by_campus: dict = {}
    for profile in profiles:
        label = campuses.label(profile.campus)
        by_campus[label] = by_campus.get(label, 0) + 1

    return schemas.AdminStatsOut(
        profiles=len(profiles),
        with_username=len([p for p in profiles if p.telegram]),
        with_bot=len([p for p in profiles if p.telegram_chat_id]),
        groups=len(groups),
        in_groups=len([p for p in profiles if p.group_id]),
        by_campus=by_campus,
    )


async def _fill_missing_usernames(db: Session, profiles: List[models.Profile]) -> None:
    """Дотягивает ники у тех, где остался только числовой ID.

    По одному ID человеку не напишешь, а выгрузка нужна как раз для связи.
    Найденные ники сохраняем — чтобы в следующий раз не ходить в Telegram.
    """
    unknown = [
        p.telegram_id
        for p in profiles
        if not p.telegram and (p.telegram_id or p.telegram_chat_id)
    ]
    if not unknown:
        return

    found = await telegram_auth.fetch_usernames([uid for uid in unknown if uid])
    if not found:
        return
    for profile in profiles:
        username = found.get(profile.telegram_id)
        if username and not profile.telegram:
            profile.telegram = username
    db.commit()


@app.get("/api/admin/export", dependencies=[Depends(require_admin)])
async def download_export(  # имя не admin_export: так звался бы и модуль рядом
    db: Session = Depends(get_db),
    fmt: str = Query("xlsx", pattern="^(xlsx|csv|json)$", alias="format"),
    scope: str = Query("full", pattern="^(full|short)$"),
    campus: Optional[str] = Query(None, pattern=campuses.PATTERN),
):
    """Выгрузка: пользователи и составы комнат.

    format: xlsx (два листа) | csv (архив из двух файлов) | json.
    scope: full — все параметры анкеты, short — только имена и ники.
    """
    query = db.query(models.Profile)
    groups_query = db.query(models.Group)
    if campus:
        query = query.filter(models.Profile.campus == campus)
        groups_query = groups_query.filter(models.Group.campus == campus)

    profiles = query.order_by(models.Profile.created_at.desc()).all()
    groups = groups_query.all()

    await _fill_missing_usernames(db, profiles)

    stamp = datetime.now().strftime("%Y-%m-%d")
    part = "kratko" if scope == admin_export.SHORT else "polno"
    base = f"kampus-oteli-{part}-{stamp}"

    if fmt == "xlsx":
        body = admin_export.to_xlsx(profiles, groups, scope)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"{base}.xlsx"
    elif fmt == "csv":
        body = admin_export.to_csv_zip(profiles, groups, scope)
        media = "application/zip"
        filename = f"{base}-csv.zip"
    else:
        body = admin_export.to_json(profiles, groups, scope)
        media = "application/json; charset=utf-8"
        filename = f"{base}.json"

    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}
