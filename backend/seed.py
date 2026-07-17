from database import SessionLocal
from models import Group, Profile

SAMPLE_PROFILES = [
    {
        "name": "Егор",
        "gender": "male",
        "photo_url": "https://randomuser.me/api/portraits/men/32.jpg",
        "telegram": "egor_dev",
        "track": "dev",
        "bio": "Пишу код по ночам, люблю тишину и порядок. Ищу спокойных соседей.",
        "room_capacity": 2,
        "sleep_schedule": "owl",
        "smoking": "no",
        "cleanliness": 4,
    },
    {
        "name": "Алина",
        "gender": "female",
        "photo_url": "https://randomuser.me/api/portraits/women/44.jpg",
        "telegram": "alina_k",
        "track": "undecided",
        "bio": "Ранняя пташка, занимаюсь йогой по утрам. За чистоту и уют в комнате.",
        "room_capacity": 3,
        "sleep_schedule": "lark",
        "smoking": "no",
        "cleanliness": 5,
    },
    {
        "name": "Тимур",
        "gender": "male",
        "photo_url": "https://randomuser.me/api/portraits/men/76.jpg",
        "telegram": "timka_777",
        "track": "business",
        "bio": "Общительный, играю на гитаре. Не против шумной компании по выходным.",
        "room_capacity": 4,
        "sleep_schedule": "any",
        "smoking": "no",
        "cleanliness": 3,
    },
    {
        "name": "Марина",
        "gender": "female",
        "photo_url": "https://randomuser.me/api/portraits/women/68.jpg",
        "telegram": "marina_art",
        "track": "design",
        "bio": "Первокурсница, рисую и веду блог. Ищу дружелюбных соседок.",
        "room_capacity": 2,
        "sleep_schedule": "owl",
        "smoking": "no",
        "cleanliness": 4,
    },
    {
        "name": "Данил",
        "gender": "male",
        "photo_url": "https://randomuser.me/api/portraits/men/12.jpg",
        "telegram": "danil_sport",
        "track": "undecided",
        "bio": "Спортсмен, встаю в 6 утра на тренировку. Ценю режим и порядок.",
        "room_capacity": 3,
        "sleep_schedule": "lark",
        "smoking": "no",
        "cleanliness": 5,
    },
    {
        "name": "Софья",
        "gender": "female",
        "photo_url": "https://randomuser.me/api/portraits/women/90.jpg",
        "telegram": "sonya_bio",
        "track": "ai",
        "bio": "Спокойная, люблю растения и чай. Комнатные цветы — моя слабость.",
        "room_capacity": 4,
        "sleep_schedule": "any",
        "smoking": "no",
        "cleanliness": 4,
    },
    {
        "name": "Артём",
        "gender": "male",
        "photo_url": "https://randomuser.me/api/portraits/men/55.jpg",
        "telegram": "artem_music",
        "track": "undecided",
        "bio": "Меломан, увлекаюсь историей и настолками. Легко нахожу общий язык.",
        "room_capacity": 2,
        "sleep_schedule": "owl",
        "smoking": "yes",
        "cleanliness": 3,
    },
    {
        "name": "Ксения",
        "gender": "female",
        "photo_url": "https://randomuser.me/api/portraits/women/25.jpg",
        "telegram": "ksusha_med",
        "track": "ai",
        "bio": "Будущий врач, много учусь. Нужна тихая и опрятная соседка.",
        "room_capacity": 3,
        "sleep_schedule": "lark",
        "smoking": "no",
        "cleanliness": 5,
    },
]


# Демо-компании: кто уже договорился жить вместе и ищет ещё соседей.
SAMPLE_GROUPS = [
    {"capacity": 3, "gender": "male", "members": ["Артём", "Тимур"]},
    {"capacity": 4, "gender": "female", "members": ["Алина", "Софья"]},
]


def seed_if_empty():
    db = SessionLocal()
    try:
        if db.query(Profile).count() == 0:
            for data in SAMPLE_PROFILES:
                db.add(Profile(**data))
            db.commit()

        # Компании сидим отдельно: анкеты могли появиться раньше этой фичи.
        if db.query(Group).count() == 0:
            for data in SAMPLE_GROUPS:
                members = (
                    db.query(Profile)
                    .filter(
                        Profile.name.in_(data["members"]),
                        Profile.gender == data["gender"],
                        Profile.group_id.is_(None),
                    )
                    .all()
                )
                if len(members) < 2:
                    continue  # некого объединять — пропускаем
                group = Group(capacity=data["capacity"], gender=data["gender"])
                db.add(group)
                db.flush()
                for member in members:
                    member.group_id = group.id
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed_if_empty()
    print("Готово: тестовые профили и компании добавлены.")
