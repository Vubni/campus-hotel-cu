"""Кампус-отели, между которыми выбирает человек.

Отличаются размерами комнат: в «Диске» бывают комнаты на 2–4 человека,
в «Облаке» — только на 2–3. Один источник правды для валидации: и анкета,
и компания, и приглашение сверяются отсюда.
"""

from typing import Tuple

DISK = "disk"
CLOUD = "cloud"

# Сервис начинался как «Кампус-отель Диск», поэтому все, кто зарегистрировался
# до появления выбора, живут именно там (см. миграцию в main.ensure_columns).
DEFAULT = DISK

PATTERN = "^(disk|cloud)$"

LABELS = {DISK: "Диск", CLOUD: "Облако"}
CAPACITIES = {DISK: (2, 3, 4), CLOUD: (2, 3)}


def label(campus: str) -> str:
    return LABELS.get(campus, LABELS[DEFAULT])


def capacities(campus: str) -> Tuple[int, ...]:
    return CAPACITIES.get(campus, CAPACITIES[DEFAULT])


def allows(campus: str, capacity: int) -> bool:
    return capacity in capacities(campus)


def capacities_text(campus: str) -> str:
    """«2, 3 или 4» — для понятного текста ошибки."""
    values = [str(c) for c in capacities(campus)]
    return f"{', '.join(values[:-1])} или {values[-1]}"
