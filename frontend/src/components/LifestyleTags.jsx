import { COOKING, GUESTS, SLEEP, SMOKING, TIDINESS, WAKEUP } from "../labels.js";

/** Общий набор бытовых тегов анкеты — в карточке соседа и в раскрытом
 *  участнике компании. Готовка теперь список, поэтому у неё несколько тегов. */
export default function LifestyleTags({ profile }) {
  const cooking = Array.isArray(profile.cooking)
    ? profile.cooking
    : [profile.cooking].filter(Boolean);

  return (
    <>
      <span className="tag">{SLEEP[profile.sleep_schedule]}</span>
      <span className="tag">{SMOKING[profile.smoking]}</span>
      <span className="tag">{TIDINESS[profile.tidiness]}</span>
      <span className="tag">{WAKEUP[profile.wakeup]}</span>
      {cooking.map((c) => (
        <span className="tag" key={c}>
          {COOKING[c]}
        </span>
      ))}
      <span className="tag">{GUESTS[profile.guests]}</span>
    </>
  );
}
