from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


TRACK_PATTERN = "^(dev|business|design|ai|undecided)$"
SMOKING_PATTERN = "^(yes|no|vape)$"


class ProfileBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    gender: str = Field(..., pattern="^(male|female|other)$")
    photo_url: str = Field("", max_length=500)
    telegram: str = Field(..., min_length=1, max_length=80)

    # Направление вместо факультета: фиксированный список из пяти.
    track: str = Field("undecided", pattern=TRACK_PATTERN)
    bio: str = ""

    # None — «не предпочтительно»: подойдёт комната любого размера.
    room_capacity: Optional[int] = Field(None, ge=2, le=4)
    sleep_schedule: str = Field("any", pattern="^(lark|owl|any)$")
    smoking: str = Field("no", pattern=SMOKING_PATTERN)
    cleanliness: int = Field(3, ge=1, le=5)


class ProfileCreate(ProfileBase):
    # Необязательное подтверждение через Telegram. Подпись проверяется на сервере
    # повторно — клиент не может сам объявить себя подтверждённым.
    telegram_auth: Optional[Dict[str, Any]] = None
    telegram_init_data: Optional[str] = None


class ProfileOut(ProfileBase):
    id: int
    created_at: datetime
    telegram_id: Optional[int] = None
    telegram_verified: bool = False
    group_id: Optional[int] = None

    class Config:
        from_attributes = True


class GroupMemberOut(BaseModel):
    """Краткая карточка участника компании."""

    id: int
    name: str
    photo_url: str = ""
    telegram: str
    track: str = "undecided"
    telegram_verified: bool = False

    class Config:
        from_attributes = True


class GroupOut(BaseModel):
    id: int
    capacity: int
    gender: str
    created_at: datetime
    members: List[GroupMemberOut] = []
    spots_left: int

    class Config:
        from_attributes = True


class GroupCreate(BaseModel):
    capacity: int = Field(..., ge=2, le=4)
    profile_id: int  # кто создаёт — он же первый участник


class GroupMembership(BaseModel):
    profile_id: int


class JoinRequestOut(BaseModel):
    id: int
    group_id: int
    status: str
    created_at: datetime
    profile: GroupMemberOut  # кто просится
    votes_needed: int  # сколько человек должны подтвердить
    votes_done: int  # сколько уже подтвердили
    approved_by: List[int] = []  # id участников, сказавших «да»

    class Config:
        from_attributes = True


class JoinRequestCreate(BaseModel):
    profile_id: int


class JoinRequestVoteIn(BaseModel):
    profile_id: int  # кто голосует (должен быть в комнате)
    approve: bool


class TelegramWidgetAuth(BaseModel):
    """Данные от Telegram Login Widget (приходят как есть из data-onauth)."""

    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str


class TelegramWebAppAuth(BaseModel):
    """initData из Telegram Mini App."""

    init_data: str


class TelegramProfileOut(BaseModel):
    """Что показываем в форме после успешного входа через Telegram."""

    telegram_id: int
    telegram: Optional[str] = None
    name: Optional[str] = None
    photo_url: Optional[str] = None


class BotLink(BaseModel):
    """/start у бота: связываем Telegram-аккаунт с анкетой."""

    telegram_id: int
    chat_id: int
    username: Optional[str] = None


class BotVote(BaseModel):
    telegram_id: int
    request_id: int
    approve: bool


class PhotoOut(BaseModel):
    photo_url: str


class ConfigOut(BaseModel):
    telegram_enabled: bool
    telegram_bot_username: Optional[str] = None
    max_upload_bytes: int
