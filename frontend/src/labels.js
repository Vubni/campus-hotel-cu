export const GENDER = { male: "М", female: "Ж", other: "Другое" };

// Направление вместо факультета — пять фиксированных вариантов.
export const TRACK = {
  dev: "Разработка",
  business: "Бизнес",
  design: "Дизайн",
  ai: "ИИ",
  undecided: "Не определился",
};

export const TRACK_OPTIONS = Object.entries(TRACK); // [[value, label], …]

export const SLEEP = {
  lark: "🌅 Жаворонок",
  owl: "🌙 Сова",
  any: "🕐 Без разницы",
};

export const SMOKING = {
  yes: "🚬 Курит",
  no: "🚭 Не курит",
  vape: "💨 Электронки",
};

// Аккуратность (бывшая «чистоплотность»): три режима.
export const TIDINESS = {
  relaxed: "🧦 Расслабленно",
  medium: "🧹 Умеренно",
  neat: "✨ Аккуратно",
};

// Подъём утром.
export const WAKEUP = {
  alarm_one: "⏰ Один будильник",
  alarm_many: "😴 Десять будильников",
  natural: "🌤️ Просыпаюсь сам",
};

// Готовка.
export const COOKING = {
  self: "🍳 Готовлю сам",
  together: "🥘 Готовим вместе",
  delivery: "🛵 Доставка и кафе",
};

// Гости.
export const GUESTS = {
  often: "🎉 Часто зову гостей",
  sometimes: "🙂 Иногда гости",
  never: "🚪 Не зову гостей",
};

export function courseLabel(course) {
  return `🎓 ${course} курс`;
}

// capacity === null — «не предпочтительно»: подойдёт комната любого размера.
export function roomLabel(capacity) {
  return capacity ? `Комната на ${capacity} чел.` : "Комната: не важно";
}
