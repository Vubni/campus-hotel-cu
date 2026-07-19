import { SPECS } from "../labels.js";

/**
 * Характеристики анкеты списком «иконка · подпись · значение».
 * Пришло на смену стене одинаковых тегов: с десятком параметров теги
 * сливались в кашу, особенно на телефоне.
 */
export default function ProfileSpecs({ profile }) {
  // Анкета, где ничего не выбрано, не должна оставлять пустую рамку с
  // разделителями — в этом случае блока просто нет.
  const filled = SPECS.filter(([, , read]) => read(profile));
  if (filled.length === 0) return null;

  return (
    <dl className="specs">
      {filled.map(([icon, label, read]) => {
        const value = read(profile);
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
