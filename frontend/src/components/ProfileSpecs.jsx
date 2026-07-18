import { SPECS } from "../labels.js";

/**
 * Характеристики анкеты списком «иконка · подпись · значение».
 * Пришло на смену стене одинаковых тегов: с десятком параметров теги
 * сливались в кашу, особенно на телефоне.
 */
export default function ProfileSpecs({ profile }) {
  return (
    <dl className="specs">
      {SPECS.map(([icon, label, read]) => {
        const value = read(profile);
        if (!value) return null; // старые анкеты без поля — просто пропускаем
        return (
          <div className="spec" key={label}>
            <span className="spec__icon" aria-hidden="true">
              {icon}
            </span>
            <span className="spec__text">
              <dt className="spec__label">{label}</dt>
              <dd className="spec__value">{value}</dd>
            </span>
          </div>
        );
      })}
    </dl>
  );
}
