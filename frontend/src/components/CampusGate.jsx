import ThemeToggle from "./ThemeToggle.jsx";
import { campusRoomsText } from "../labels.js";

/**
 * Самый первый экран: в каком кампус-отеле человек живёт.
 *
 * Идёт до выбора пола, потому что определяет вообще всё остальное — ленту,
 * компании и то, комнаты какого размера бывают.
 */
export default function CampusGate({ onSelect }) {
  return (
    <div className="gate">
      <div className="gate__theme">
        <ThemeToggle />
      </div>
      <div className="gate__inner">
        <div className="gate__brand">
          <span className="gate__logo">🏠</span>
          Кампус-отели
        </div>

        <h1 className="gate__title">
          Где ты будешь <span className="accent">жить?</span>
        </h1>
        <p className="gate__subtitle">
          Соседей ищем внутри одного кампус-отеля.
          <br />
          Выбери свой — потом его можно поменять в анкете.
        </p>

        <div className="gate__options">
          <button className="gate__option" onClick={() => onSelect("disk")}>
            <span className="gate__emoji">💽</span>
            <span className="gate__label">Диск</span>
            <span className="gate__hint">
              Комнаты на {campusRoomsText("disk")} человека
            </span>
          </button>

          <button className="gate__option" onClick={() => onSelect("cloud")}>
            <span className="gate__emoji">☁️</span>
            <span className="gate__label">Облако</span>
            <span className="gate__hint">
              Комнаты на {campusRoomsText("cloud")} человека
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}
