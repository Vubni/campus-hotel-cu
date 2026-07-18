from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


TRACK_PATTERN = "^(dev|business|design|ai|undecided)$"
SMOKING_PATTERN = "^(yes|no|vape)$"
TIDINESS_PATTERN = "^(relaxed|medium|neat)$"
WAKEUP_PATTERN = "^(alarm_one|alarm_many|natural)$"
GUESTS_PATTERN = "^(often|sometimes|never)$"
SHOWER_PATTERN = "^(morning|evening|any)$"
TEMPERATURE_PATTERN = "^(cool|medium|warm)$"
NOISE_PATTERN = "^(quiet|headphones|loud)$"
ALCOHOL_PATTERN = "^(no|sometimes|often)$"

COOKING_VALUES = ("self", "together", "delivery")
# Для фильтра: одно значение из списка готовки.
COOKING_ITEM_PATTERN = "^(self|together|delivery)$"


def normalize_cooking(value) -> List[str]:
    """Готовка допускает несколько вариантов. Принимаем список или строку
    через запятую (как хранится в БД), чистим от мусора и дублей.
    Пустой выбор недопустим — тогда возвращаем ['self'].
    """
    if value is None:
        items = []
    elif isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, (list, tuple)):
        items = list(value)
    else:
        items = []
    result: List[str] = []
    for item in items:
        key = str(item).strip()
        if key in COOKING_VALUES and key not in result:
            result.append(key)
    return result or ["self"]


class ProfileBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    gender: str = Field(..., pattern="^(male|female|other)$")
    photo_url: str = Field("", max_length=500)
    telegram: str = Field(..., min_length=1, max_length=80)

    # Направление вместо факультета: фиксированный список из пяти.
    track: str = Field("undecided", pattern=TRACK_PATTERN)
    course: int = Field(1, ge=1, le=6)
    bio: str = ""

    # None — «не предпочтительно»: подойдёт комната любого размера.
    room_capacity: Optional[int] = Field(None, ge=2, le=4)
    sleep_schedule: str = Field("any", pattern="^(lark|owl|any)$")
    smoking: str = Field("no", pattern=SMOKING_PATTERN)
    tidiness: str = Field("medium", pattern=TIDINESS_PATTERN)
    wakeup: str = Field("alarm_one", pattern=WAKEUP_PATTERN)
    # Несколько вариантов готовки; хранится строкой через запятую, наружу — список.
    cooking: List[str] = Field(default_factory=lambda: ["self"])
    guests: str = Field("sometimes", pattern=GUESTS_PATTERN)
    shower: str = Field("any", pattern=SHOWER_PATTERN)
    temperature: str = Field("medium", pattern=TEMPERATURE_PATTERN)
    noise: str = Field("headphones", pattern=NOISE_PATTERN)
    alcohol: str = Field("sometimes", pattern=ALCOHOL_PATTERN)

    @field_validator("cooking", mode="before")
    @classmethod
    def _validate_cooking(cls, value):
        return normalize_cooking(value)


class ProfileCreate(ProfileBase):
    # Необязательное подтверждение через Telegram. Подпись проверяется на сервере
    # повторно — клиент не может сам объявить себя подтверждённым.
    telegram_auth: Optional[Dict[str, Any]] = None
    telegram_init_data: Optional[str] = None


class ProfileUpdate(ProfileBase):
    """Редактирование своей анкеты.

    Пол и подтверждённый Telegram сервер менять не даёт — см. update_profile.
    """


class ProfileOut(ProfileBase):
    id: int
    created_at: datetime
    telegram_id: Optional[int] = None
    telegram_verified: bool = False
    group_id: Optional[int] = None

    class Config:
        from_attributes = True


class GroupMemberOut(BaseModel):
    """Карточка участника компании.

    Помимо краткой части несёт бытовые поля — чтобы в разделе «Компании» можно
    было раскрыть участника и решить, стоит ли к нему проситься.
    """

    id: int
    name: str
    photo_url: str = ""
    telegram: str
    track: str = "undecided"
    telegram_verified: bool = False

    course: int = 1
    bio: str = ""
    room_capacity: Optional[int] = None
    sleep_schedule: str = "any"
    smoking: str = "no"
    tidiness: str = "medium"
    wakeup: str = "alarm_one"
    cooking: List[str] = Field(default_factory=lambda: ["self"])
    guests: str = "sometimes"
    shower: str = "any"
    temperature: str = "medium"
    noise: str = "headphones"
    alcohol: str = "sometimes"

    @field_validator("cooking", mode="before")
    @classmethod
    def _validate_cooking(cls, value):
        return normalize_cooking(value)

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
