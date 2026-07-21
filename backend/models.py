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

import campuses
from database import Base


class Block(Base):
    """Блок — две комнаты с общим входом, всего на 6 человек.

    Бывает только в «Диске» (см. campuses.py). Сочетания ровно два: 2+4 и 3+3,
    поэтому в собранном блоке всегда две комнаты — третью уже не вместить.
    """

    __tablename__ = "blocks"

    id = Column(Integer, primary_key=True, index=True)
    # Пол блока: соседи по блоку делят вход, поэтому правило то же, что у комнат.
    gender = Column(String(20), nullable=False)
    campus = Column(String(20), nullable=False, default="disk")
    created_at = Column(DateTime, default=datetime.utcnow)

    groups = relationship("Group", back_populates="block")

    @property
    def taken(self) -> int:
        """Сколько мест блока уже разобрано комнатами (не людьми)."""
        return sum(g.capacity for g in self.groups)

    @property
    def spots_left(self) -> int:
        return campuses.BLOCK_SIZE - self.taken


class Group(Base):
    """Комната — группа людей, которые решили жить вместе.

    Никаких секций и номеров: capacity — это на сколько человек комната,
    а свободные места = capacity - число участников.
    """

    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    # Сколько человек в комнате. Допустимые значения зависят от кампус-отеля:
    # в «Диске» 2–4, в «Облаке» 2–3 (см. campuses.py). Меняется и после
    # создания — комната на 4 может ужаться до 2, если больше не набралось.
    capacity = Column(Integer, nullable=False, default=3)
    # Пол комнаты: парни живут с парнями, девушки — с девушками.
    gender = Column(String(20), nullable=False)
    # Кампус-отель: disk | cloud. Комнаты разных отелей не смешиваются.
    campus = Column(String(20), nullable=False, default="disk")
    # Блок, в который комната объединилась с другой. Пусто — блока пока нет.
    block_id = Column(Integer, ForeignKey("blocks.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    block = relationship("Block", back_populates="groups")
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
    # Кампус-отель: disk | cloud. Видно только тех, кто выбрал тот же самый.
    campus = Column(String(20), nullable=False, default="disk")
    # Либо /api/media/<file>.jpg (загруженное фото или скачанный аватар),
    # либо внешняя ссылка у старых записей.
    photo_url = Column(String(500), nullable=False, default="")
    telegram = Column(String(80), nullable=False)  # username без @

    # Заполняются, если анкету подтвердили входом через Telegram.
    telegram_id = Column(BigInteger, nullable=True)
    telegram_verified = Column(Boolean, nullable=False, default=False)
    # Появляется после /start у бота — только тогда можно слать уведомления.
    telegram_chat_id = Column(BigInteger, nullable=True)

    # Пусто — человек ищет соседей сам по себе; заполнено — уже в комнате.
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    group = relationship("Group", back_populates="members")

    # Ниже "" означает «не выбрано»: человек
    # ещё не ответил, и мы не показываем характеристику вместо того, чтобы
    # подставлять выдуманное значение.
    # Направление: dev | business | design | ai | undecided | ""
    track = Column(String(20), nullable=False, default="")
    course = Column(Integer, nullable=False, default=1)  # курс 1..4, по умолчанию 1
    bio = Column(Text, nullable=False, default="")

    # Желаемые размеры комнаты — можно выбрать несколько: «хочу 3 или 4, но не
    # двухместную». Храним как список через запятую ("3,4"), "" — «не важно»,
    # подойдёт любая. Пришло на смену одиночному room_capacity.
    room_capacities = Column(String(20), nullable=False, default="")
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
    """Заявка на вступление в комнату.

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
    """Приглашение собрать комнату прямо из ленты анкет.

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


class BlockRequest(Base):
    """Заявка одной комнаты объединиться в блок с другой.

    Блок появляется не сразу: предложение должны подтвердить ВСЕ жильцы
    комнаты, которую позвали. Любой отказ — заявка отклонена. Устроено так же,
    как вступление в комнату, только решают целой комнатой, а не поодиночке.
    """

    __tablename__ = "block_requests"

    id = Column(Integer, primary_key=True, index=True)
    from_group_id = Column(
        Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    to_group_id = Column(
        Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    # pending | approved | rejected | cancelled
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    decided_at = Column(DateTime, nullable=True)

    from_group = relationship("Group", foreign_keys=[from_group_id])
    to_group = relationship("Group", foreign_keys=[to_group_id])
    votes = relationship(
        "BlockRequestVote", back_populates="request", cascade="all, delete-orphan"
    )


class BlockRequestVote(Base):
    """Голос жильца позванной комнаты по заявке на блок."""

    __tablename__ = "block_request_votes"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(
        Integer, ForeignKey("block_requests.id", ondelete="CASCADE"), nullable=False
    )
    member_id = Column(
        Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    approve = Column(Boolean, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    request = relationship("BlockRequest", back_populates="votes")
    member = relationship("Profile", foreign_keys=[member_id])
