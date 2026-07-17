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

export function cleanlinessLabel(level) {
  return "🧹".repeat(level) + `  ${level}/5`;
}

// capacity === null — «не предпочтительно»: подойдёт комната любого размера.
export function roomLabel(capacity) {
  return capacity ? `Комната на ${capacity} чел.` : "Комната: не важно";
}
