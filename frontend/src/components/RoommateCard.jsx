import {
  COOKING,
  GENDER,
  GUESTS,
  SLEEP,
  SMOKING,
  TIDINESS,
  TRACK,
  WAKEUP,
  courseLabel,
  roomLabel,
} from "../labels.js";

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
    sleep_schedule,
    smoking,
    tidiness,
    wakeup,
    cooking,
    guests,
    telegram_verified,
  } = profile;

  return (
    <article className="card">
      <div className="card__photo">
        {photo_url ? (
          <img src={photo_url} alt={name} loading="lazy" />
        ) : (
          <div className="card__placeholder">{initials(name)}</div>
        )}
        <span className="card__room">{roomLabel(room_capacity)}</span>
      </div>

      <div className="card__body">
        <h3 className="card__name">
          {name}
          {telegram_verified && (
            <span className="card__verified" title="Профиль подтверждён через Telegram">
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

        {bio && <p className="card__bio">{bio}</p>}

        <div className="card__tags">
          <span className="tag">{SLEEP[sleep_schedule]}</span>
          <span className="tag">{SMOKING[smoking]}</span>
          <span className="tag">{TIDINESS[tidiness]}</span>
          <span className="tag">{WAKEUP[wakeup]}</span>
          <span className="tag">{COOKING[cooking]}</span>
          <span className="tag">{GUESTS[guests]}</span>
        </div>

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
      </div>
    </article>
  );
}
