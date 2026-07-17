"""Логика заявок на вступление.

Правило: заявку должны подтвердить ВСЕ, кто сейчас в комнате. Любой отказ —
заявка отклонена. Голоса тех, кто успел выйти, не учитываются.
"""

from datetime import datetime
from typing import List

from sqlalchemy.orm import Session

import models

PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
CANCELLED = "cancelled"


def active_votes(req: models.JoinRequest) -> dict:
    """Голоса только от тех, кто сейчас в комнате.

    Если участник вышел, его голос перестаёт учитываться — иначе заявка
    зависла бы навсегда в ожидании ушедшего.
    """
    member_ids = {m.id for m in req.group.members}
    return {v.member_id: v.approve for v in req.votes if v.member_id in member_ids}


def votes_needed(req: models.JoinRequest) -> int:
    return len(req.group.members)


def votes_done(req: models.JoinRequest) -> int:
    return len([a for a in active_votes(req).values() if a is True])


def evaluate(db: Session, req: models.JoinRequest) -> str:
    """Пересчитывает статус заявки после голоса или изменения состава.

    Возвращает итоговый статус: pending | approved | rejected.
    """
    if req.status != PENDING:
        return req.status

    group = req.group
    member_ids = {m.id for m in group.members}
    votes = active_votes(req)

    # Хотя бы один против — сразу отказ.
    if any(approve is False for approve in votes.values()):
        req.status = REJECTED
        req.decided_at = datetime.utcnow()
        return REJECTED

    # Компания опустела — решать некому, заявка теряет смысл.
    if not member_ids:
        req.status = CANCELLED
        req.decided_at = datetime.utcnow()
        return CANCELLED

    # Ждём, пока проголосуют все.
    if not all(mid in votes for mid in member_ids):
        return PENDING

    # Все «за», но пока голосовали, места могли кончиться.
    if group.spots_left <= 0:
        req.status = REJECTED
        req.decided_at = datetime.utcnow()
        return REJECTED

    req.profile.group_id = group.id
    req.status = APPROVED
    req.decided_at = datetime.utcnow()
    return APPROVED


def close_obsolete(db: Session, profile: models.Profile, group: models.Group) -> List[models.JoinRequest]:
    """После вступления человека убираем ставшие ненужными заявки.

    Возвращает заявки, чьих авторов стоит уведомить об отказе.
    """
    rejected = []

    # Свои остальные заявки — человек уже определился.
    others = (
        db.query(models.JoinRequest)
        .filter(
            models.JoinRequest.profile_id == profile.id,
            models.JoinRequest.status == PENDING,
            models.JoinRequest.group_id != group.id,
        )
        .all()
    )
    for req in others:
        req.status = CANCELLED
        req.decided_at = datetime.utcnow()

    # Если мест не осталось — остальным в эту компанию отказываем.
    if group.spots_left <= 0:
        pending = (
            db.query(models.JoinRequest)
            .filter(
                models.JoinRequest.group_id == group.id,
                models.JoinRequest.status == PENDING,
            )
            .all()
        )
        for req in pending:
            req.status = REJECTED
            req.decided_at = datetime.utcnow()
            rejected.append(req)

    return rejected
