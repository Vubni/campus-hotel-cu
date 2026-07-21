"""Кампус-отели, между которыми выбирает человек.

Отличаются размерами комнат: в «Диске» бывают комнаты на 2–4 человека,
в «Облаке» — только на 2–3. Один источник правды для валидации: и анкета,
и комната, и приглашение сверяются отсюда.

Ещё одно отличие: в «Диске» комнаты объединяются в блоки по 6 человек
(2+4 или 3+3), в «Облаке» блоков нет.
"""

from typing import Optional, Tuple

DISK = "disk"
CLOUD = "cloud"

# Сервис начинался как «Кампус-отель Диск», поэтому все, кто зарегистрировался
# до появления выбора, живут именно там (см. миграцию в main.ensure_columns).
DEFAULT = DISK

PATTERN = "^(disk|cloud)$"

LABELS = {DISK: "Диск", CLOUD: "Облако"}
CAPACITIES = {DISK: (2, 3, 4), CLOUD: (2, 3)}

# Сколько человек в блоке и где блоки вообще бывают. Блок — это две комнаты
# с общим входом: 2+4 или 3+3. Третью комнату в блок не добавить, поэтому
# «блок собран» = в нём две комнаты.
BLOCK_SIZE = 6
WITH_BLOCKS = (DISK,)


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


def has_blocks(campus: str) -> bool:
    return campus in WITH_BLOCKS


def block_partner(campus: str, capacity: int) -> Optional[int]:
    """Размер комнаты, с которой эта соберёт полный блок.

    None — пары не существует: либо в отеле нет блоков, либо такой комнаты
    в нём не бывает (в «Диске» пара всегда есть: 2↔4, 3↔3).
    """
    if not has_blocks(campus):
        return None
    partner = BLOCK_SIZE - capacity
    return partner if allows(campus, partner) else None
