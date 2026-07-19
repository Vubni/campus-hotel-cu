from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from database import Base


class Group(Base):
    """Компания — просто группа людей, которые решили жить вместе.

    Никаких секций и номеров комнат: capacity — это на сколько человек комната,
    а свободные места = capacity - число участников.
    """

    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    capacity = Column(Integer, nullable=False, default=3)  # 2..4
    # Пол компании: парни живут с парнями, девушки — с девушками.
    gender = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    members = relationship("Profile", back_populates="group")
    requests = relationship(
        "JoinRequest", back_populates="group", cascade="all, delete-orphan"
    )

    @property
    def spots_left(self) -> int:
        return self.capacity - len(self.members)


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(80), nullable=False)
    # Возраст и курс больше не собираются и не показываются. Колонки оставлены
    # nullable, чтобы не терять уже введённые данные и легко вернуть поля.
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=False)  # "male" | "female" | "other"
    # Либо /api/media/<file>.jpg (загруженное фото или скачанный аватар),
    # либо внешняя ссылка у старых записей.
    photo_url = Column(String(500), nullable=False, default="")
    telegram = Column(String(80), nullable=False)  # username без @

    # Заполняются, если анкету подтвердили входом через Telegram.
    telegram_id = Column(BigInteger, nullable=True)
    telegram_verified = Column(Boolean, nullable=False, default=False)
    # Появляется после /start у бота — только тогда можно слать уведомления.
    telegram_chat_id = Column(BigInteger, nullable=True)

    # Пусто — человек ищет соседей сам по себе; заполнено — уже в компании.
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    group = relationship("Group", back_populates="members")

    # Ниже "" (и NULL у course/room_capacity) означает «не выбрано»: человек
    # ещё не ответил, и мы не показываем характеристику вместо того, чтобы
    # подставлять выдуманное значение.
    # Направление: dev | business | design | ai | undecided | ""
    track = Column(String(20), nullable=False, default="")
    course = Column(Integer, nullable=True)  # курс 1..6, NULL — не выбран
    bio = Column(Text, nullable=False, default="")

    # 2, 3, 4 или NULL — «не предпочтительно», подойдёт любая комната.
    # Без default: SQLAlchemy подставляет его вместо None, и NULL было бы не задать.
    room_capacity = Column(Integer, nullable=True)
    sleep_schedule = Column(String(20), nullable=False, default="")  # lark | owl | any
    smoking = Column(String(20), nullable=False, default="")  # yes | no | vape
    # Аккуратность (бывшая «чистоплотность»): relaxed | medium | neat
    tidiness = Column(String(20), nullable=False, default="")
    # Подъём утром: alarm_one (1 будильник) | alarm_many (10 будильников) | natural (само)
    wakeup = Column(String(20), nullable=False, default="")
    # Готовка: можно выбрать несколько из self | together | delivery.
    # Храним как список значений через запятую ("self,together"), "" — не выбрано.
    cooking = Column(String(60), nullable=False, default="")
    # Гости: often (часто) | sometimes (иногда) | never (не зову)
    guests = Column(String(20), nullable=False, default="")
    # Душ: morning (утром) | evening (вечером) | any (когда как)
    shower = Column(String(20), nullable=False, default="")
    # Температура в комнате: cool (прохладно) | medium (нормально) | warm (тепло)
    temperature = Column(String(20), nullable=False, default="")
    # Звук: quiet (тишина) | headphones (в наушниках) | loud (музыка вслух)
    noise = Column(String(20), nullable=False, default="")
    # Алкоголь: no (не пью) | sometimes (иногда) | often (часто)
    alcohol = Column(String(20), nullable=False, default="")

    created_at = Column(DateTime, default=datetime.utcnow)


class JoinRequest(Base):
    """Заявка на вступление в компанию.

    Человек не попадает в комнату сам: заявку должны подтвердить ВСЕ, кто уже
    в ней. Любой отказ — заявка отклонена.
    """

    __tablename__ = "join_requests"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(
        Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    profile_id = Column(
        Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    # pending | approved | rejected | cancelled
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    decided_at = Column(DateTime, nullable=True)

    group = relationship("Group", back_populates="requests")
    profile = relationship("Profile", foreign_keys=[profile_id])
    votes = relationship(
        "JoinRequestVote", back_populates="request", cascade="all, delete-orphan"
    )


class GroupInvite(Base):
    """Приглашение собрать компанию прямо из ленты анкет.

    Комната НЕ создаётся в момент приглашения: пока позванный не согласится,
    существует только запись-приглашение. Согласился — создаём группу и кладём
    туда обоих.
    """

    __tablename__ = "group_invites"

    id = Column(Integer, primary_key=True, index=True)
    from_profile_id = Column(
        Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    to_profile_id = Column(
        Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    capacity = Column(Integer, nullable=False, default=2)  # 2..4
    # pending | accepted | declined | cancelled
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    decided_at = Column(DateTime, nullable=True)

    from_profile = relationship("Profile", foreign_keys=[from_profile_id])
    to_profile = relationship("Profile", foreign_keys=[to_profile_id])


class JoinRequestVote(Base):
    """Голос одного участника комнаты по заявке."""

    __tablename__ = "join_request_votes"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(
        Integer, ForeignKey("join_requests.id", ondelete="CASCADE"), nullable=False
    )
    member_id = Column(
        Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    approve = Column(Boolean, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    request = relationship("JoinRequest", back_populates="votes")
    member = relationship("Profile", foreign_keys=[member_id])
