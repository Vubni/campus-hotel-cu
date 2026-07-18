import { GENDER, TRACK, roomLabel } from "../labels.js";
import ProfileSpecs from "./ProfileSpecs.jsx";

function initials(name) {
  return name.trim().charAt(0).toUpperCase();
}

export default function RoommateCard({ profile }) {
  const {
    name,
    gender,
    photo_url,
    telegram,
    track,
    course,
    bio,
    room_capacity,
    telegram_verified,
  } = profile;

  return (
    <article className="card">
      {/* Шапка: квадратное фото и то, кто это. Дальше — всё на всю ширину,
          иначе на телефоне детали ютились бы в узкой колонке справа. */}
      <div className="card__top">
        <div className="card__photo">
          {photo_url ? (
            <img src={photo_url} alt={name} loading="lazy" />
          ) : (
            <div className="card__placeholder">{initials(name)}</div>
          )}
        </div>

        <div className="card__head">
          <h3 className="card__name">
            {name}
            {telegram_verified && (
              <span
                className="card__verified"
                title="Профиль подтверждён через Telegram"
              >
                ✓
              </span>
            )}
            <span className="card__gender">{GENDER[gender]}</span>
          </h3>

          <p className="card__faculty">
            {[TRACK[track], course ? `${course} курс` : null]
              .filter(Boolean)
              .join(" · ")}
          </p>

          <span className="card__room">{roomLabel(room_capacity)}</span>
        </div>
      </div>

      {bio && <p className="card__bio">{bio}</p>}

      <ProfileSpecs profile={profile} />

      <a
        className="card__tg"
        href={`https://t.me/${telegram}`}
        target="_blank"
        rel="noreferrer"
      >
        <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
          <path
            fill="currentColor"
            d="M9.78 18.65l.28-4.23 7.68-6.92c.34-.31-.07-.46-.52-.19L7.74 13.3 3.64 12c-.88-.25-.89-.86.2-1.3l15.97-6.16c.73-.33 1.43.18 1.15 1.3l-2.72 12.81c-.19.91-.74 1.13-1.5.71L12.6 16.3l-1.99 1.93c-.23.23-.42.42-.83.42z"
          />
        </svg>
        Написать в Telegram
      </a>
    </article>
  );
}
