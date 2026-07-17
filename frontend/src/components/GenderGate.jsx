import ThemeToggle from "./ThemeToggle.jsx";

export default function GenderGate({ onSelect }) {
  return (
    <div className="gate">
      <div className="gate__theme">
        <ThemeToggle />
      </div>
      <div className="gate__inner">
        <div className="gate__brand">
          <span className="gate__logo">🏠</span>
          Кампус-отель Диск
        </div>

        <h1 className="gate__title">
          С кем ты будешь <span className="accent">жить?</span>
        </h1>
        <p className="gate__subtitle">
          Парни живут с парнями, девушки — с девушками.
          <br />
          Выбери, кого показывать в ленте.
        </p>

        <div className="gate__options">
          <button
            className="gate__option"
            onClick={() => onSelect("male")}
          >
            <span className="gate__emoji">🧑</span>
            <span className="gate__label">Я парень</span>
            <span className="gate__hint">Показать парней</span>
          </button>

          <button
            className="gate__option"
            onClick={() => onSelect("female")}
          >
            <span className="gate__emoji">👩</span>
            <span className="gate__label">Я девушка</span>
            <span className="gate__hint">Показать девушек</span>
          </button>
        </div>
      </div>
    </div>
  );
}
