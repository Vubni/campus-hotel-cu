export const GENDER = { male: "М", female: "Ж", other: "Другое" };

// Кампус-отели. Отличаются размерами комнат: в «Облаке» на четверых не селят.
// Держим в одном месте — то же самое продублировано на бэке в campuses.py.
export const DEFAULT_CAMPUS = "disk";
export const CAMPUS = { disk: "Диск", cloud: "Облако" };
const CAMPUS_CAPACITIES = { disk: [2, 3, 4], cloud: [2, 3] };

// Блок — две комнаты с общим входом, вместе на 6 человек: 2+4 или 3+3.
// Бывает только в «Диске».
export const BLOCK_SIZE = 6;
const CAMPUS_WITH_BLOCKS = ["disk"];

/** Какие комнаты бывают в этом кампус-отеле: [2, 3, 4] или [2, 3]. */
export function campusCapacities(campus) {
  return CAMPUS_CAPACITIES[campus] || CAMPUS_CAPACITIES[DEFAULT_CAMPUS];
}

/** Есть ли в этом кампус-отеле блоки. */
export function campusHasBlocks(campus) {
  return CAMPUS_WITH_BLOCKS.includes(campus);
}

/**
 * Комната какого размера соберёт с этой полный блок.
 * null — пары не существует (в отеле нет блоков или такой комнаты там не бывает).
 */
export function blockPartner(campus, capacity) {
  if (!campusHasBlocks(campus)) return null;
  const partner = BLOCK_SIZE - capacity;
  return campusCapacities(campus).includes(partner) ? partner : null;
}

/** «2–4» / «2–3» — для подписей вроде «Комнаты на 2–3 человека». */
export function campusRoomsText(campus) {
  const sizes = campusCapacities(campus);
  return `${sizes[0]}–${sizes[sizes.length - 1]}`;
}

// На бакалавриате всего 4 курса — столько и предлагаем.
export const COURSES = [1, 2, 3, 4];

// Направление вместо факультета — пять фиксированных вариантов.
export const TRACK = {
  dev: "Разработка",
  business: "Бизнес",
  design: "Дизайн",
  ai: "ИИ",
  undecided: "Не определился",
};

export const TRACK_OPTIONS = Object.entries(TRACK); // [[value, label], …]

// Подписи значений — без эмодзи: иконка живёт отдельно, в описании характеристики.
export const SLEEP = { lark: "Жаворонок", owl: "Сова", any: "Без разницы" };
export const SMOKING = { no: "Не курит", yes: "Курит", vape: "Электронки" };
export const TIDINESS = {
  relaxed: "Расслабленно",
  medium: "Умеренно",
  neat: "Аккуратно",
};
export const WAKEUP = {
  alarm_one: "Один будильник",
  alarm_many: "Десять будильников",
  natural: "Просыпается сам",
};
export const COOKING = { self: "Сам", together: "Вместе", delivery: "Доставка" };
export const GUESTS = { often: "Часто", sometimes: "Иногда", never: "Не зовёт" };
export const SHOWER = { morning: "Утром", evening: "Вечером", any: "Когда как" };
export const TEMPERATURE = {
  cool: "Прохладно",
  medium: "Нормально",
  warm: "Тепло",
};
export const NOISE = {
  quiet: "Тишина",
  headphones: "В наушниках",
  loud: "Музыка вслух",
};
export const ALCOHOL = { no: "Не пьёт", sometimes: "Иногда", often: "Часто" };

/** Готовка — список, поэтому подписи склеиваем: «Сам, вместе». */
export function cookingLabel(value) {
  const items = Array.isArray(value) ? value : [value].filter(Boolean);
  return items
    .map((key, i) => {
      const label = COOKING[key] || "";
      return i === 0 ? label : label.toLowerCase();
    })
    .filter(Boolean)
    .join(", ");
}

/**
 * Желаемые размеры комнаты: их может быть несколько («3 или 4»).
 * Пустой список — «не важно», подойдёт комната любого размера.
 */
export function roomLabel(capacities) {
  const sizes = Array.isArray(capacities)
    ? capacities
    : [capacities].filter(Boolean);
  if (sizes.length === 0) return "Комната: не важно";
  return `Комната на ${sizes.join(" или ")} чел.`;
}

/**
 * Характеристики анкеты для показа: [иконка, подпись, значение].
 * Один источник правды — используется и в карточке, и в раскрытом участнике.
 */
export const SPECS = [
  ["🌙", "Режим сна", (p) => SLEEP[p.sleep_schedule]],
  ["⏰", "Подъём", (p) => WAKEUP[p.wakeup]],
  ["🚿", "Душ", (p) => SHOWER[p.shower]],
  ["✨", "Аккуратность", (p) => TIDINESS[p.tidiness]],
  ["🌡️", "Температура", (p) => TEMPERATURE[p.temperature]],
  ["🔊", "Звук", (p) => NOISE[p.noise]],
  ["🍳", "Готовка", (p) => cookingLabel(p.cooking)],
  ["🎉", "Гости", (p) => GUESTS[p.guests]],
  ["🚭", "Курение", (p) => SMOKING[p.smoking]],
  ["🍻", "Алкоголь", (p) => ALCOHOL[p.alcohol]],
];
