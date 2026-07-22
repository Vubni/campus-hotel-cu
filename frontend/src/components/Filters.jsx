import { useMemo, useState } from "react";
import { COURSES, TRACK_OPTIONS, campusCapacities } from "../labels.js";

// [ключ фильтра, подпись «любой», [[значение, подпись], …]]
// Размер комнаты подставляется отдельно: он зависит от кампус-отеля.
const FILTER_SELECTS = [
  ["track", "Направление", TRACK_OPTIONS],
  ["course", "Курс", COURSES.map((c) => [String(c), `${c} курс`])],
  ["room_capacity", "Комната", []],
  [
    "sleep_schedule",
    "Режим сна",
    [
      ["lark", "Жаворонок"],
      ["owl", "Сова"],
      ["any", "Без разницы"],
    ],
  ],
  [
    "smoking",
    "Курение",
    [
      ["no", "Не курит"],
      ["yes", "Курит"],
      ["vape", "Электронки"],
    ],
  ],
  [
    "tidiness",
    "Аккуратность",
    [
      ["relaxed", "Расслабленно"],
      ["medium", "Умеренно"],
      ["neat", "Аккуратно"],
    ],
  ],
  [
    "wakeup",
    "Подъём",
    [
      ["alarm_one", "Один будильник"],
      ["alarm_many", "Десять будильников"],
      ["natural", "Просыпается сам"],
    ],
  ],
  [
    "cooking",
    "Готовка",
    [
      ["self", "Готовит сам"],
      ["together", "Готовит вместе"],
      ["delivery", "Доставка / кафе"],
    ],
  ],
  [
    "guests",
    "Гости",
    [
      ["often", "Часто зовёт"],
      ["sometimes", "Иногда"],
      ["never", "Не зовёт"],
    ],
  ],
  [
    "shower",
    "Душ",
    [
      ["morning", "Утром"],
      ["evening", "Вечером"],
      ["any", "Когда как"],
    ],
  ],
  [
    "temperature",
    "Температура",
    [
      ["cool", "Прохладно"],
      ["medium", "Нормально"],
      ["warm", "Тепло"],
    ],
  ],
  [
    "noise",
    "Звук",
    [
      ["quiet", "Тишина"],
      ["headphones", "В наушниках"],
      ["loud", "Музыка вслух"],
    ],
  ],
  [
    "alcohol",
    "Алкоголь",
    [
      ["no", "Не пьёт"],
      ["sometimes", "Иногда"],
      ["often", "Часто"],
    ],
  ],
];

export default function Filters({
  filters,
  campus,
  onChange,
  onReset,
  // Сколько нашлось людей, у которых совпали все мои параметры, и включён ли
  // показ только их. Ноль — кнопки нет: обещать «идеального соседа» и
  // показывать пустоту хуже, чем промолчать.
  idealCount = 0,
  idealOn = false,
  onToggleIdeal,
}) {
  // Фильтров стало много — прячем их за кнопку, чтобы не занимали пол-экрана.
  const [open, setOpen] = useState(false);
  const set = (key) => (e) => onChange({ ...filters, [key]: e.target.value });

  // Комнаты на 4 предлагаем искать только там, где они есть.
  const selects = useMemo(
    () =>
      FILTER_SELECTS.map((item) =>
        item[0] === "room_capacity"
          ? [
              item[0],
              item[1],
              campusCapacities(campus).map((n) => [String(n), `${n} человека`]),
            ]
          : item
      ),
    [campus]
  );

  // Поиск всегда на виду, поэтому в счётчик активных фильтров его не считаем.
  const activeCount = FILTER_SELECTS.filter(
    ([key]) => filters[key] !== "" && filters[key] !== undefined
  ).length;

  return (
    <div className="filters">
      <div className="filters__bar">
        <input
          className="filters__search"
          type="text"
          placeholder="Поиск по имени и описанию…"
          value={filters.search}
          onChange={set("search")}
        />
        <button
          type="button"
          className={`filters__toggle${open ? " filters__toggle--on" : ""}`}
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
        >
          Фильтры
          {activeCount > 0 && (
            <span className="filters__badge">{activeCount}</span>
          )}
          <span aria-hidden="true">{open ? "▲" : "▼"}</span>
        </button>
      </div>

      {idealCount > 0 && (
        <button
          type="button"
          className={`filters__ideal${idealOn ? " filters__ideal--on" : ""}`}
          onClick={onToggleIdeal}
          aria-pressed={idealOn}
        >
          <span aria-hidden="true">✨</span>
          {idealOn ? "Показать всех" : "Показать идеального соседа"}
          <span className="filters__ideal-count">{idealCount}</span>
        </button>
      )}

      {open && (
        <div className="filters__panel">
          {selects.map(([key, anyLabel, options]) => (
            <select key={key} value={filters[key]} onChange={set(key)}>
              <option value="">{anyLabel}</option>
              {options.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          ))}
          <button className="filters__reset" onClick={onReset}>
            Сбросить фильтры
          </button>
        </div>
      )}
    </div>
  );
}
