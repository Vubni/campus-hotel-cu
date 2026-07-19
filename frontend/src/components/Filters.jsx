import { useState } from "react";
import { TRACK_OPTIONS } from "../labels.js";

// [ключ фильтра, подпись «любой», [[значение, подпись], …]]
const FILTER_SELECTS = [
  ["track", "Направление", TRACK_OPTIONS],
  [
    "course",
    "Курс",
    [1, 2, 3, 4, 5, 6].map((c) => [String(c), `${c} курс`]),
  ],
  [
    "room_capacity",
    "Комната",
    [
      ["2", "2 человека"],
      ["3", "3 человека"],
      ["4", "4 человека"],
    ],
  ],
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

export default function Filters({ filters, onChange, onReset }) {
  // Фильтров стало много — прячем их за кнопку, чтобы не занимали пол-экрана.
  const [open, setOpen] = useState(false);
  const set = (key) => (e) => onChange({ ...filters, [key]: e.target.value });

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

      {open && (
        <div className="filters__panel">
          {FILTER_SELECTS.map(([key, anyLabel, options]) => (
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
