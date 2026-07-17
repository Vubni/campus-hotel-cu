from datetime import datetime
from typing import List, Optional

from fastapi import (
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

import config
import join_flow
import models
import notifier
import schemas
import storage
import telegram_auth
from database import Base, engine, get_db, wait_for_db
from seed import seed_if_empty

app = FastAPI(title="Кампус-отель Диск — поиск соседей", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

        # Возраст и курс больше не обязательны — их перестали собирать.
        conn.execute(text("ALTER TABLE profiles ALTER COLUMN age DROP NOT NULL"))

        # NULL в room_capacity = «не предпочтительно».
        conn.execute(
            text("ALTER TABLE profiles ALTER COLUMN room_capacity DROP NOT NULL")
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


@app.on_event("startup")
def on_startup():
    wait_for_db()
    Base.metadata.create_all(bind=engine)
    ensure_columns()
    seed_if_empty()
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    # Раздаём загруженные фото. Монтируем после старта, когда папка точно есть.
    app.mount(
        storage.PUBLIC_PREFIX,
        StaticFiles(directory=config.UPLOAD_DIR),
        name="media",
    )


@app.get("/api/config", response_model=schemas.ConfigOut)
def get_config():
    """Фронтенд спрашивает, показывать ли кнопку входа через Telegram."""
    return schemas.ConfigOut(
        telegram_enabled=config.telegram_enabled(),
        telegram_bot_username=config.TELEGRAM_BOT_USERNAME or None,
        max_upload_bytes=config.MAX_UPLOAD_BYTES,
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


@app.get("/api/profiles", response_model=List[schemas.ProfileOut])
def list_profiles(
    db: Session = Depends(get_db),
    gender: Optional[str] = Query(None, pattern="^(male|female|other)$"),
    room_capacity: Optional[int] = Query(None, ge=2, le=4),
    smoking: Optional[str] = Query(None, pattern=schemas.SMOKING_PATTERN),
    sleep_schedule: Optional[str] = Query(None, pattern="^(lark|owl|any)$"),
    track: Optional[str] = Query(None, pattern=schemas.TRACK_PATTERN),
    search: Optional[str] = Query(None),
    without_group: Optional[bool] = Query(
        None, description="true — только те, кто ещё не в компании"
    ),
):
    query = db.query(models.Profile)
    if gender:
        query = query.filter(models.Profile.gender == gender)
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
    if search:
        # Направление теперь выбирается фильтром, а не ищется текстом.
        like = f"%{search.lower()}%"
        query = query.filter(
            (models.Profile.name.ilike(like)) | (models.Profile.bio.ilike(like))
        )
    return query.order_by(models.Profile.created_at.desc()).all()


@app.get("/api/profiles/{profile_id}", response_model=schemas.ProfileOut)
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

    profile = models.Profile(**data)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


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


async def _notify_members_about_request(req: models.JoinRequest) -> None:
    """Заявка ушла — зовём подтвердить всех, кто в комнате."""
    who = _who(req.profile)
    needed = join_flow.votes_needed(req)
    for member in req.group.members:
        if not member.telegram_chat_id:
            continue
        await notifier.send_message(
            member.telegram_chat_id,
            f"🔔 <b>{who}</b> просится к вам в комнату на {req.group.capacity}.\n"
            f"@{req.profile.telegram}\n\n"
            f"Нужно согласие всех участников ({needed}).",
            reply_markup=notifier.vote_keyboard(req.id),
        )


async def _notify_decision(req: models.JoinRequest, status: str) -> None:
    """Сообщаем автору заявки итог."""
    profile = req.profile
    if not profile.telegram_chat_id:
        return
    if status == join_flow.APPROVED:
        mates = ", ".join(m.name for m in req.group.members if m.id != profile.id)
        await notifier.send_message(
            profile.telegram_chat_id,
            f"🎉 Тебя приняли в комнату на {req.group.capacity}!\n"
            f"Соседи: {mates or '—'}\n\n{config.SITE_URL}",
        )
    elif status == join_flow.REJECTED:
        await notifier.send_message(
            profile.telegram_chat_id,
            "😔 Заявку в комнату отклонили. Не расстраивайся — "
            f"есть другие варианты: {config.SITE_URL}",
        )
    elif status == join_flow.CANCELLED:
        await notifier.send_message(
            profile.telegram_chat_id,
            "ℹ️ Заявка отменена: компания распалась.",
        )


async def _apply_vote(
    db: Session, req: models.JoinRequest, voter: models.Profile, approve: bool
) -> str:
    """Записывает голос, пересчитывает статус и рассылает уведомления."""
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

    if status != join_flow.PENDING:
        await _notify_decision(req, status)
    if status == join_flow.APPROVED:
        # Остальным в комнате — что состав пополнился.
        for member in req.group.members:
            if member.id != req.profile_id and member.telegram_chat_id:
                await notifier.send_message(
                    member.telegram_chat_id,
                    f"✅ <b>{req.profile.name}</b> теперь в вашей комнате.",
                )
        for other in also_rejected:
            await _notify_decision(other, join_flow.REJECTED)
    return status


@app.get("/api/groups", response_model=List[schemas.GroupOut])
def list_groups(
    db: Session = Depends(get_db),
    gender: Optional[str] = Query(None, pattern="^(male|female|other)$"),
    only_open: Optional[bool] = Query(None, description="true — только с местами"),
):
    query = db.query(models.Group)
    if gender:
        query = query.filter(models.Group.gender == gender)
    groups = query.order_by(models.Group.created_at.desc()).all()
    if only_open:
        groups = [g for g in groups if g.spots_left > 0]
    return groups


@app.get("/api/groups/{group_id}", response_model=schemas.GroupOut)
def get_group(group_id: int, db: Session = Depends(get_db)):
    return _get_group_or_404(db, group_id)


@app.post("/api/groups", response_model=schemas.GroupOut, status_code=201)
def create_group(payload: schemas.GroupCreate, db: Session = Depends(get_db)):
    """Создаёт компанию: автор сразу становится первым участником."""
    profile = _get_profile_or_404(db, payload.profile_id)
    if profile.group_id:
        raise HTTPException(status_code=409, detail="Ты уже состоишь в компании")

    group = models.Group(capacity=payload.capacity, gender=profile.gender)
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
):
    group = _get_group_or_404(db, group_id)
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
):
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
async def create_join_request(
    group_id: int, payload: schemas.JoinRequestCreate, db: Session = Depends(get_db)
):
    """Заявка на вступление. Сама по себе в комнату не пускает."""
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

    await _notify_members_about_request(req)
    return _request_out(req)


@app.post("/api/requests/{request_id}/vote", response_model=schemas.JoinRequestOut)
async def vote_request(
    request_id: int, payload: schemas.JoinRequestVoteIn, db: Session = Depends(get_db)
):
    req = _get_request_or_404(db, request_id)
    voter = _get_profile_or_404(db, payload.profile_id)

    if req.status != join_flow.PENDING:
        raise HTTPException(status_code=409, detail="Заявка уже закрыта")
    if voter.group_id != req.group_id:
        raise HTTPException(
            status_code=403, detail="Голосовать могут только те, кто в комнате"
        )

    status = await _apply_vote(db, req, voter, payload.approve)
    db.refresh(req)
    return _request_out(req)


@app.post("/api/requests/{request_id}/cancel", status_code=204)
def cancel_request(
    request_id: int, payload: schemas.GroupMembership, db: Session = Depends(get_db)
):
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
async def leave_group(
    group_id: int, payload: schemas.GroupMembership, db: Session = Depends(get_db)
):
    group = _get_group_or_404(db, group_id)
    profile = _get_profile_or_404(db, payload.profile_id)
    if profile.group_id != group.id:
        raise HTTPException(status_code=409, detail="Ты не состоишь в этой компании")

    profile.group_id = None
    db.flush()
    db.refresh(group)

    leftovers = list(group.members)
    left_name = profile.name

    # Состав изменился — часть заявок могла «дозреть» без ушедшего.
    decided = []
    for req in list(group.requests):
        if req.status == join_flow.PENDING:
            new_status = join_flow.evaluate(db, req)
            if new_status != join_flow.PENDING:
                decided.append((req, new_status))

    # Пустая компания никому не нужна — удаляем.
    if not group.members:
        db.delete(group)
    db.commit()

    for member in leftovers:
        if member.telegram_chat_id:
            await notifier.send_message(
                member.telegram_chat_id,
                f"🚪 <b>{left_name}</b> вышел(а) из вашей комнаты.\n"
                f"Свободных мест стало больше: {config.SITE_URL}",
            )
    for req, status in decided:
        await _notify_decision(req, status)
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
async def bot_vote(payload: schemas.BotVote, db: Session = Depends(get_db)):
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

    status = await _apply_vote(db, req, profile, payload.approve)
    db.refresh(req)
    return {
        "status": status,
        "votes_done": join_flow.votes_done(req),
        "votes_needed": join_flow.votes_needed(req),
        "who": req.profile.name,
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}
