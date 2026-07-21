"""Логика объединения комнат в блоки.

Блок — две комнаты на 6 человек вместе: 2+4 или 3+3. Правило подтверждения то
же, что у заявок в комнату: предложение должны принять ВСЕ жильцы позванной
комнаты, любой отказ — отклонено. Голоса тех, кто успел съехать, не считаются.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

import campuses
import models

PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
CANCELLED = "cancelled"


def active_votes(req: models.BlockRequest) -> dict:
    """Голоса только от тех, кто сейчас живёт в позванной комнате."""
    member_ids = {m.id for m in req.to_group.members}
    return {v.member_id: v.approve for v in req.votes if v.member_id in member_ids}


def votes_needed(req: models.BlockRequest) -> int:
    return len(req.to_group.members)


def votes_done(req: models.BlockRequest) -> int:
    return len([a for a in active_votes(req).values() if a is True])


def pair_problem(
    group: models.Group, other: models.Group
) -> Optional[str]:
    """Почему эти две комнаты не соберут блок. None — всё в порядке.

    Один источник правды: проверяется и при отправке заявки, и при подсчёте
    голосов — пока комната думала, её размер могли поменять.
    """
    if group.id == other.id:
        return "Комната не объединяется сама с собой"
    if not campuses.has_blocks(group.campus):
        return (
            f"В кампус-отеле «{campuses.label(group.campus)}» блоков нет — "
            "комнаты там не объединяются"
        )
    if group.campus != other.campus:
        return "Комнаты в разных кампус-отелях"
    if group.gender != other.gender:
        return "Блок общий: парни живут с парнями, девушки — с девушками"
    if group.block_id:
        return "Твоя комната уже в блоке"
    if other.block_id:
        return "Эта комната уже в блоке"
    if group.capacity + other.capacity != campuses.BLOCK_SIZE:
        return (
            f"В блоке {campuses.BLOCK_SIZE} человек: комната на {group.capacity} "
            f"объединяется только с комнатой на "
            f"{campuses.BLOCK_SIZE - group.capacity}"
        )
    return None


def evaluate(db: Session, req: models.BlockRequest) -> str:
    """Пересчитывает статус заявки после голоса или изменения состава.

    Возвращает итоговый статус: pending | approved | rejected | cancelled.
    """
    if req.status != PENDING:
        return req.status

    votes = active_votes(req)

    # Хотя бы один против — сразу отказ.
    if any(approve is False for approve in votes.values()):
        req.status = REJECTED
        req.decided_at = datetime.utcnow()
        return REJECTED

    member_ids = {m.id for m in req.to_group.members}
    # Комната опустела — решать некому.
    if not member_ids:
        req.status = CANCELLED
        req.decided_at = datetime.utcnow()
        return CANCELLED

    # Ждём, пока выскажутся все.
    if not all(mid in votes for mid in member_ids):
        return PENDING

    # Все «за», но пока голосовали, комнаты могли измениться: кто-то ужал
    # размер или успел собрать блок с другими.
    if pair_problem(req.from_group, req.to_group):
        req.status = REJECTED
        req.decided_at = datetime.utcnow()
        return REJECTED

    block = models.Block(
        gender=req.from_group.gender, campus=req.from_group.campus
    )
    db.add(block)
    db.flush()  # нужен id до привязки комнат
    req.from_group.block_id = block.id
    req.to_group.block_id = block.id

    req.status = APPROVED
    req.decided_at = datetime.utcnow()
    return APPROVED


def close_obsolete(
    db: Session, groups: List[models.Group], keep: models.BlockRequest
) -> List[models.BlockRequest]:
    """Гасит прочие заявки этих комнат — блок они уже собрали.

    Возвращает заявки, чьих отправителей стоит уведомить об отказе.
    """
    ids = [g.id for g in groups]
    others = (
        db.query(models.BlockRequest)
        .filter(
            models.BlockRequest.id != keep.id,
            models.BlockRequest.status == PENDING,
            models.BlockRequest.from_group_id.in_(ids)
            | models.BlockRequest.to_group_id.in_(ids),
        )
        .all()
    )
    for req in others:
        req.status = REJECTED
        req.decided_at = datetime.utcnow()
    return others


def dissolve(db: Session, block: models.Block) -> None:
    """Распускает блок: комнаты снова сами по себе.

    Блок из одной комнаты не имеет смысла — вторая половина всё равно пустая,
    поэтому выход одной комнаты распускает его целиком.
    """
    for group in list(block.groups):
        group.block_id = None
    db.flush()
    db.delete(block)


def cancel_for_group(db: Session, group: models.Group) -> List[models.BlockRequest]:
    """Закрывает висящие заявки комнаты — она выбыла или изменилась.

    Возвращает закрытые заявки: их участникам стоит сказать, что ждать нечего.
    """
    reqs = (
        db.query(models.BlockRequest)
        .filter(
            models.BlockRequest.status == PENDING,
            (models.BlockRequest.from_group_id == group.id)
            | (models.BlockRequest.to_group_id == group.id),
        )
        .all()
    )
    for req in reqs:
        req.status = CANCELLED
        req.decided_at = datetime.utcnow()
    return reqs
