import { TRACK_OPTIONS } from "../labels.js";

export default function Filters({ filters, onChange, onReset }) {
  const set = (key) => (e) => onChange({ ...filters, [key]: e.target.value });

  return (
    <div className="filters">
      <input
        className="filters__search"
        type="text"
        placeholder="Поиск по имени и описанию…"
        value={filters.search}
        onChange={set("search")}
      />

      <select value={filters.track} onChange={set("track")}>
        <option value="">Направление: любое</option>
        {TRACK_OPTIONS.map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>

      <select value={filters.room_capacity} onChange={set("room_capacity")}>
        <option value="">Комната: любая</option>
        <option value="2">2 человека</option>
        <option value="3">3 человека</option>
        <option value="4">4 человека</option>
      </select>

      <select value={filters.sleep_schedule} onChange={set("sleep_schedule")}>
        <option value="">Режим: любой</option>
        <option value="lark">Жаворонок</option>
        <option value="owl">Сова</option>
        <option value="any">Без разницы</option>
      </select>

      <select value={filters.smoking} onChange={set("smoking")}>
        <option value="">Курение: любое</option>
        <option value="no">Не курит</option>
        <option value="yes">Курит</option>
        <option value="vape">Электронки</option>
      </select>

      <button className="filters__reset" onClick={onReset}>
        Сбросить
      </button>
    </div>
  );
}
