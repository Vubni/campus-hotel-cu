import { BLOCK_SIZE, TRACK, blockPartner, campusHasBlocks } from "../labels.js";

/** Комната в списке блока: состав в одну строку, без раскрытия. */
function RoomMini({ group, title, tone = "" }) {
  // Направление — в скобках: через «·» имена и направления слиплись бы в
  // сплошной список, где непонятно, где кончается один человек.
  const who = group.members
    .map((m) => (TRACK[m.track] ? `${m.name} (${TRACK[m.track]})` : m.name))
    .join(", ");
  return (
    <div className={`broom${tone ? ` broom--${tone}` : ""}`}>
      <div className="broom__head">
        <span className="broom__size">на {group.capacity}</span>
        {title && <span className="broom__title">{title}</span>}
        <span className="broom__count">
          {group.members.length}/{group.capacity}
        </span>
      </div>
      <p className="broom__who">{who || "Пока пусто"}</p>
      {group.spots_left > 0 && (
        <p className="broom__free">
          Ещё ищут {group.spots_left} — места в блоке уже забронированы
        </p>
      )}
    </div>
  );
}

/**
 * Раздел «Блок». Блок — две комнаты с общим входом, вместе на 6 человек:
 * 2+4 или 3+3. Объединяются комнатами, а не людьми, поэтому почти всё здесь
 * доступно только тем, кто уже собрал комнату.
 */
export default function BlockPanel({
  campus,
  myProfile,
  myGroup,
  myBlock,
  candidates = [],
  requests = [],
  onRequestBlock,
  onVoteBlock,
  onCancelBlock,
  onLeaveBlock,
  busy,
}) {
  if (!campusHasBlocks(campus)) {
    return (
      <p className="state">
        В этом кампус-отеле комнаты не объединяются в блоки — раздел нужен
        только в «Диске».
      </p>
    );
  }

  if (!myProfile) {
    return (
      <p className="state">
        Размести анкету и собери комнату — тогда её можно будет объединить
        с другой в блок на {BLOCK_SIZE} человек.
      </p>
    );
  }

  if (!myGroup) {
    return (
      <p className="state">
        В блок объединяются комнатами, а не поодиночке. Сначала собери комнату
        во вкладке «Комнаты» — потом сможешь позвать в блок соседей.
      </p>
    );
  }

  // Блок собран — показываем обе комнаты и выход.
  if (myBlock) {
    const mine = myBlock.groups.find((g) => g.id === myGroup.id);
    const others = myBlock.groups.filter((g) => g.id !== myGroup.id);
    return (
      <div className="block">
        <div className="block__head">
          <h3 className="block__title">🧩 Блок собран</h3>
          <p className="block__sub">
            {myBlock.groups.map((g) => g.capacity).join(" + ")} ={" "}
            {myBlock.taken} человек
          </p>
        </div>
        <div className="block__rooms">
          {mine && <RoomMini group={mine} title="твоя комната" tone="mine" />}
          {others.map((g) => (
            <RoomMini key={g.id} group={g} title="соседи по блоку" />
          ))}
        </div>
        <button
          className="block__leave"
          onClick={() => onLeaveBlock(myBlock.id)}
          disabled={busy}
        >
          Выйти из блока
        </button>
        <p className="block__hint">
          Блок распадётся для обеих комнат — вторая половина без вас всё равно
          не наберётся.
        </p>
      </div>
    );
  }

  const partner = blockPartner(campus, myGroup.capacity);
  const incoming = requests.filter((r) => r.to_group_id === myGroup.id);
  const outgoing = requests.filter((r) => r.from_group_id === myGroup.id);
  // Комнаты, с которыми предложение уже висит — в любую сторону. Они показаны
  // выше («Вас зовут» / «Вы позвали»), и звать их второй раз бессмысленно:
  // получилась бы встречная заявка о том же самом.
  const pending = new Set([
    ...outgoing.map((r) => r.to_group_id),
    ...incoming.map((r) => r.from_group_id),
  ]);
  const free = candidates.filter((g) => !pending.has(g.id));

  return (
    <div className="block">
      <div className="block__head">
        <h3 className="block__title">Блок на {BLOCK_SIZE} человек</h3>
        <p className="block__sub">
          Твоя комната на {myGroup.capacity} — нужна комната на {partner}.
          Вместе получится {myGroup.capacity}+{partner}.
        </p>
      </div>

      {/* Входящие: решают все жильцы комнаты, поэтому видно, сколько уже «за». */}
      {incoming.length > 0 && (
        <div className="block__section">
          <p className="block__section-title">Вас зовут в блок</p>
          {incoming.map((r) => {
            const iVoted = r.approved_by.includes(myProfile.id);
            return (
              <div className="breq" key={r.id}>
                <RoomMini group={r.from_group} />
                <p className="breq__votes">
                  Согласились {r.votes_done} из {r.votes_needed} — нужно
                  согласие всех, кто живёт в твоей комнате
                </p>
                {iVoted ? (
                  <span className="breq__waiting">
                    Ты согласи(лся/лась) — ждём остальных
                  </span>
                ) : (
                  <div className="breq__actions">
                    <button
                      className="breq__yes"
                      onClick={() => onVoteBlock(r.id, true)}
                      disabled={busy}
                    >
                      Объединиться
                    </button>
                    <button
                      className="breq__no"
                      onClick={() => onVoteBlock(r.id, false)}
                      disabled={busy}
                    >
                      Отказаться
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {outgoing.length > 0 && (
        <div className="block__section">
          <p className="block__section-title">Вы позвали</p>
          {outgoing.map((r) => (
            <div className="breq" key={r.id}>
              <RoomMini group={r.to_group} />
              <p className="breq__votes">
                ⏳ Ждём ответа · согласились {r.votes_done} из {r.votes_needed}
              </p>
              <button
                className="breq__cancel"
                onClick={() => onCancelBlock(r.id)}
                disabled={busy}
              >
                Отозвать
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="block__section">
        <p className="block__section-title">
          Комнаты на {partner} — с ними получится полный блок
        </p>
        {free.length === 0 ? (
          <p className="state">
            {candidates.length > 0
              ? "Других подходящих комнат нет — ответьте на предложение выше."
              : `Подходящих комнат пока нет. Как только кто-то соберёт комнату на ${partner}, она появится здесь.`}
          </p>
        ) : (
          <div className="block__candidates">
            {free.map((g) => (
              <div className="bcand" key={g.id}>
                <RoomMini group={g} />
                <button
                  className="bcand__btn"
                  onClick={() => onRequestBlock(g.id)}
                  disabled={busy}
                >
                  Позвать в блок
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
