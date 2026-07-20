import { useState } from "react";
import { TRACK, roomLabel } from "../labels.js";
import ProfileSpecs from "./ProfileSpecs.jsx";

const SPOTS_WORD = (n) => (n === 1 ? "место" : n < 5 ? "места" : "мест");

function Avatar({ person, className = "" }) {
  const initial = (person.name || "?").trim().charAt(0).toUpperCase();
  return (
    <span className={`gmember__ava ${className}`}>
      {person.photo_url ? (
        <img src={person.photo_url} alt={person.name} loading="lazy" />
      ) : (
        initial
      )}
    </span>
  );
}

function Member({ member }) {
  // Раскрытие: даже если человек уже в компании, можно посмотреть его анкету
  // и решить, стоит ли к нему проситься.
  const [open, setOpen] = useState(false);
  const meta = [TRACK[member.track], member.course ? `${member.course} курс` : null]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className={`gmember-box${open ? " gmember-box--open" : ""}`}>
      <button
        type="button"
        className="gmember gmember--toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <Avatar person={member} />
        <span className="gmember__info">
          <span className="gmember__name">
            {member.name}
            {member.telegram_verified && <span className="card__verified">✓</span>}
          </span>
          <span className="gmember__meta">{meta || `@${member.telegram}`}</span>
        </span>
        <span className="gmember__chevron" aria-hidden="true">
          {open ? "Скрыть ▲" : "Подробнее ▼"}
        </span>
      </button>

      {open && (
        <div className="gmember__details">
          {member.bio && <p className="gmember__bio">{member.bio}</p>}
          <span className="card__room">{roomLabel(member.room_capacity)}</span>
          <ProfileSpecs profile={member} />
          <a
            className="gmember__tg"
            href={`https://t.me/${member.telegram}`}
            target="_blank"
            rel="noreferrer"
          >
            Написать в Telegram
          </a>
        </div>
      )}
    </div>
  );
}

/** Заявка глазами жильца комнаты: можно принять или отклонить. */
function RequestRow({ request, myProfile, onVote, busy }) {
  const iVoted = request.approved_by.includes(myProfile?.id);
  return (
    <div className="greq">
      <Avatar person={request.profile} />
      <div className="greq__info">
        <span className="gmember__name">{request.profile.name}</span>
        <span className="gmember__meta">
          {TRACK[request.profile.track] || `@${request.profile.telegram}`} · подтвердили{" "}
          {request.votes_done} из {request.votes_needed}
        </span>
      </div>
      {iVoted ? (
        <span className="greq__waiting">Ждём остальных</span>
      ) : (
        <div className="greq__actions">
          <button
            className="greq__yes"
            onClick={() => onVote(request.id, true)}
            disabled={busy}
            title="Принять"
          >
            ✓
          </button>
          <button
            className="greq__no"
            onClick={() => onVote(request.id, false)}
            disabled={busy}
            title="Отклонить"
          >
            ✕
          </button>
        </div>
      )}
    </div>
  );
}

export default function GroupCard({
  group,
  myProfile,
  requests = [],
  myRequestHere,
  onRequest,
  onCancelRequest,
  onVote,
  onLeave,
  onChangeCapacity,
  capacities = [2, 3, 4],
  busy,
}) {
  const { id, capacity, members, spots_left } = group;
  const full = spots_left <= 0;
  const iAmMember = members.some((m) => m.id === myProfile?.id);
  const canRequest =
    myProfile &&
    !iAmMember &&
    !myProfile.group_id &&
    !full &&
    !myRequestHere &&
    myProfile.gender === group.gender;

  let hint = null;
  if (!myProfile) hint = "Размести анкету, чтобы подать заявку";
  else if (!iAmMember && myProfile.group_id) hint = "Ты уже в другой компании";
  else if (!iAmMember && full) hint = "Мест нет";

  return (
    <article className={`gcard${full ? " gcard--full" : ""}`}>
      <div className="gcard__head">
        <div>
          <h3 className="gcard__title">Комната на {capacity}</h3>
          <p className="gcard__status">
            {full ? (
              "Состав собран"
            ) : (
              <>
                Ищут ещё <strong>{spots_left}</strong> — свободно {spots_left}{" "}
                {SPOTS_WORD(spots_left)}
              </>
            )}
          </p>
        </div>
        <span className="gcard__count">
          {members.length}/{capacity}
        </span>
      </div>

      <div className="gcard__members">
        {members.map((m) => (
          <Member key={m.id} member={m} />
        ))}
        {Array.from({ length: spots_left }).map((_, i) => (
          <div className="gmember gmember--empty" key={`free-${i}`}>
            <span className="gmember__ava gmember__ava--empty">+</span>
            <span className="gmember__info">
              <span className="gmember__name">Свободное место</span>
              <span className="gmember__meta">Может, это ты?</span>
            </span>
          </div>
        ))}
      </div>

      {/* Заявки видят только жильцы этой комнаты */}
      {iAmMember && requests.length > 0 && (
        <div className="gcard__requests">
          <p className="gcard__requests-title">
            Заявки · нужно согласие всех {members.length}
          </p>
          {requests.map((r) => (
            <RequestRow
              key={r.id}
              request={r}
              myProfile={myProfile}
              onVote={onVote}
              busy={busy}
            />
          ))}
        </div>
      )}

      {/* Планы меняются: собирались вчетвером, а набралось двое — комнату
          можно ужать, не распуская компанию. Меньше, чем вас уже есть, —
          нельзя, поэтому такие размеры недоступны. */}
      {iAmMember && typeof onChangeCapacity === "function" && (
        <div className="gcard__resize">
          <span className="gcard__resize-label">Размер комнаты:</span>
          <div className="gcard__resize-btns">
            {capacities.map((n) => (
              <button
                key={n}
                className={`gcard__resize-btn${
                  n === capacity ? " gcard__resize-btn--on" : ""
                }`}
                onClick={() => onChangeCapacity(id, n)}
                disabled={busy || n === capacity || n < members.length}
                title={
                  n < members.length
                    ? `Вас уже ${members.length} — не поместитесь`
                    : `Сделать комнатой на ${n}`
                }
                aria-pressed={n === capacity}
              >
                на {n}
              </button>
            ))}
          </div>
        </div>
      )}

      {iAmMember ? (
        <button className="gcard__leave" onClick={() => onLeave(id)} disabled={busy}>
          Выйти из компании
        </button>
      ) : myRequestHere ? (
        <div className="gcard__pending">
          <span>
            ⏳ Заявка отправлена · подтвердили {myRequestHere.votes_done} из{" "}
            {myRequestHere.votes_needed}
          </span>
          <button
            className="gcard__cancel"
            onClick={() => onCancelRequest(myRequestHere.id)}
            disabled={busy}
          >
            Отменить
          </button>
        </div>
      ) : canRequest ? (
        <button className="gcard__join" onClick={() => onRequest(id)} disabled={busy}>
          Подать заявку
        </button>
      ) : hint ? (
        <p className="gcard__hint">{hint}</p>
      ) : null}
    </article>
  );
}
