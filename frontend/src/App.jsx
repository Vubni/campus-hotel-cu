import { useEffect, useState } from "react";
import {
  cancelRequest,
  changeGroupCapacity,
  createGroup,
  createInvite,
  fetchConfig,
  fetchGroupRequests,
  fetchGroups,
  fetchMyInvites,
  fetchMyRequests,
  respondInvite,
  fetchProfiles,
  leaveGroup,
  requestJoin,
  voteRequest,
} from "./api.js";
import RoommateCard from "./components/RoommateCard.jsx";
import GroupCard from "./components/GroupCard.jsx";
import Filters from "./components/Filters.jsx";
import AddProfileModal from "./components/AddProfileModal.jsx";
import AdminPanel from "./components/AdminPanel.jsx";
import GenderGate from "./components/GenderGate.jsx";
import CampusGate from "./components/CampusGate.jsx";
import ThemeToggle from "./components/ThemeToggle.jsx";
import { CAMPUS, campusCapacities, campusRoomsText } from "./labels.js";
import { initWebApp } from "./telegram.js";
import { useMyProfile } from "./useMyProfile.js";

const GENDER_KEY = "obshaga_gender";
const CAMPUS_KEY = "obshaga_campus";

const EMPTY_FILTERS = {
  search: "",
  track: "",
  course: "",
  room_capacity: "",
  sleep_schedule: "",
  smoking: "",
  tidiness: "",
  wakeup: "",
  cooking: "",
  guests: "",
  shower: "",
  temperature: "",
  noise: "",
  alcohol: "",
};

const GENDER_WORD = { male: "Парни", female: "Девушки" };

export default function App() {
  const [gender, setGender] = useState(
    () => localStorage.getItem(GENDER_KEY) || ""
  );
  // Кампус-отель. Пока анкеты нет — выбор с первого экрана, дальше главной
  // остаётся анкета: там его и меняют, отсюда мы значение только подхватываем.
  const [campus, setCampus] = useState(
    () => localStorage.getItem(CAMPUS_KEY) || ""
  );
  const [tab, setTab] = useState("singles"); // "singles" | "groups"

  const [profiles, setProfiles] = useState([]);
  const [groups, setGroups] = useState([]);
  // Заявки в мою комнату (id заявки → голосуем) и мои исходящие заявки.
  const [incoming, setIncoming] = useState([]);
  const [myRequests, setMyRequests] = useState([]);
  // Мои исходящие приглашения «давай жить вместе» — чтобы не звать дважды.
  const [myInvites, setMyInvites] = useState([]);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [modal, setModal] = useState(null); // null | "create" | "edit" | "admin"
  const [busy, setBusy] = useState(false);
  // Админка своя только у владельцев — решает сервер по подписи Telegram.
  const [isAdmin, setIsAdmin] = useState(false);

  const { myProfile, loadingMe, remember, forget, reloadMe } = useMyProfile();

  function chooseGender(value) {
    localStorage.setItem(GENDER_KEY, value);
    setGender(value);
  }

  function chooseCampus(value) {
    localStorage.setItem(CAMPUS_KEY, value);
    setCampus(value);
  }

  /** Вернуться к выбору кампус-отеля. Только пока анкеты нет: дальше решает она. */
  function resetCampus() {
    localStorage.removeItem(CAMPUS_KEY);
    setCampus("");
  }

  async function load(currentFilters, currentGender, currentCampus) {
    setLoading(true);
    setError("");
    try {
      // Одиночки — те, кто ещё не в компании; компании грузим отдельно.
      const [people, companies] = await Promise.all([
        fetchProfiles({
          ...currentFilters,
          gender: currentGender,
          campus: currentCampus,
          without_group: true,
        }),
        fetchGroups({ gender: currentGender, campus: currentCampus }),
      ]);
      setProfiles(people);
      setGroups(companies);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  /** Заявки грузим только там, где они нужны: в свою комнату и свои исходящие. */
  async function loadRequests(me) {
    if (!me) {
      setIncoming([]);
      setMyRequests([]);
      setMyInvites([]);
      return;
    }
    try {
      const [mine, inbox, invites] = await Promise.all([
        fetchMyRequests(me.id),
        me.group_id ? fetchGroupRequests(me.group_id) : Promise.resolve([]),
        fetchMyInvites(me.id),
      ]);
      setMyRequests(mine);
      setIncoming(inbox);
      setMyInvites(invites);
    } catch {
      // Заявки — не критично: лента должна работать и без них.
      setIncoming([]);
    }
  }

  // Если сайт открыт внутри Telegram — разворачиваем окно Mini App.
  useEffect(() => {
    initWebApp();
    fetchConfig()
      .then((cfg) => setIsAdmin(Boolean(cfg.is_admin)))
      .catch(() => setIsAdmin(false));
  }, []);

  useEffect(() => {
    if (!gender || !campus) return;
    const id = setTimeout(() => load(filters, gender, campus), 250);
    return () => clearTimeout(id);
  }, [filters, gender, campus]);

  // Анкета — источник правды про кампус-отель: сменили его в анкете (или зашли с
  // другого устройства) — лента должна переехать следом.
  useEffect(() => {
    if (myProfile?.campus && myProfile.campus !== campus) {
      chooseCampus(myProfile.campus);
    }
  }, [myProfile, campus]);

  // Фильтр «комната на 4» пережил переезд в «Облако» — там таких нет, и лента
  // молча оказалась бы пустой. Сбрасываем сами.
  useEffect(() => {
    if (!campus || !filters.room_capacity) return;
    const allowed = campusCapacities(campus).map(String);
    if (!allowed.includes(String(filters.room_capacity))) {
      setFilters((prev) => ({ ...prev, room_capacity: "" }));
    }
  }, [campus, filters.room_capacity]);

  function handleCreated(profile) {
    setModal(null);
    setFilters(EMPTY_FILTERS);
    remember(profile); // запоминаем как «мою анкету»
    setProfiles((prev) => [profile, ...prev]);
  }

  function handleUpdated(profile) {
    setModal(null);
    remember(profile); // обновляем «мою анкету»
    // Если анкета в ленте (без компании) — освежаем её на месте.
    setProfiles((prev) => prev.map((p) => (p.id === profile.id ? profile : p)));
  }

  async function handleDeleted() {
    setModal(null);
    forget();
    await refresh();
  }

  useEffect(() => {
    loadRequests(myProfile);
  }, [myProfile]);

  async function refresh() {
    const [, me] = await Promise.all([
      load(filters, gender, campus),
      reloadMe(),
    ]);
    await loadRequests(me || myProfile);
  }

  async function withBusy(action) {
    setBusy(true);
    setError("");
    try {
      await action();
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const handleRequest = (groupId) =>
    withBusy(() => requestJoin(groupId, myProfile.id));

  const handleCancelRequest = (requestId) =>
    withBusy(() => cancelRequest(requestId, myProfile.id));

  const handleVote = (requestId, approve) =>
    withBusy(() => voteRequest(requestId, myProfile.id, approve));

  const handleLeave = (groupId) =>
    withBusy(() => leaveGroup(groupId, myProfile.id));

  const handleCreateGroup = (capacity) =>
    withBusy(() => createGroup(capacity, myProfile.id));

  // Комнату можно сузить и расширить: собрались на 4, а набралось двое.
  const handleChangeCapacity = (groupId, capacity) =>
    withBusy(() => changeGroupCapacity(groupId, myProfile.id, capacity));

  // Позвать жить вместе: комната появится только когда человек согласится.
  const handleInvite = (toProfileId, capacity) =>
    withBusy(() => createInvite(myProfile.id, toProfileId, capacity));

  const handleRespondInvite = (inviteId, accept) =>
    withBusy(() => respondInvite(inviteId, myProfile.id, accept));

  // Кампус-отель определяет и ленту, и размеры комнат — спрашиваем его первым.
  if (!campus) {
    return <CampusGate onSelect={chooseCampus} />;
  }

  if (!gender) {
    return <GenderGate campus={campus} onSelect={chooseGender} />;
  }

  // Приглашения ко мне — их надо показать в самом приложении: бот доходит
  // только до тех, кто нажимал /start.
  const incomingInvites = myInvites.filter(
    (i) => i.to_profile_id === myProfile?.id
  );
  const openGroups = groups.filter((g) => g.spots_left > 0);
  const canStartGroup = myProfile && !myProfile.group_id;
  const capacities = campusCapacities(campus);
  // Пусто из-за фильтров или тут вообще никого нет — это разные сообщения.
  const filtersActive = Object.values(filters).some((v) => v !== "");

  return (
    <div className="app">
      <header className="header">
        <div className="header__inner">
          <div className="header__brand">
            <span className="header__logo">🏠</span>
            <div>
              <h1>Кампус-отель {CAMPUS[campus]}</h1>
              <p>Найди соседа по комнате</p>
            </div>
          </div>

          <div className="header__right">
            <ThemeToggle compact />
            {isAdmin && (
              <button
                className="header__admin"
                onClick={() => setModal("admin")}
                title="Выгрузка данных"
              >
                <span className="header__admin-full">Админка</span>
                <span className="header__admin-icon" aria-hidden="true">
                  ⚙
                </span>
              </button>
            )}
            {/* Пока анкеты нет, отель можно перевыбрать здесь. С анкетой
                она хранится в ней — и меняется только там, чтобы случайное
                нажатие не выкинуло человека из компании. */}
            {myProfile ? (
              <span
                className="header__campus"
                title="Сменить кампус-отель можно в анкете"
              >
                {CAMPUS[campus]}
              </span>
            ) : (
              <button
                className="header__gender"
                onClick={resetCampus}
                title="Сменить"
              >
                {CAMPUS[campus]}
                <span className="header__gender-change">сменить</span>
              </button>
            )}
            <button
              className="header__gender"
              onClick={() => setGender("")}
              title="Сменить"
            >
              {GENDER_WORD[gender]}
              <span className="header__gender-change">сменить</span>
            </button>
            {myProfile ? (
              <button
                className="header__cta"
                onClick={() => setModal("edit")}
              >
                <span className="header__cta-full">Моя анкета</span>
                <span className="header__cta-short">Анкета</span>
                <span className="header__cta-icon" aria-hidden="true">✎</span>
              </button>
            ) : (
              <button
                className="header__cta"
                onClick={() => setModal("create")}
              >
                <span className="header__cta-full">Разместить анкету</span>
                <span className="header__cta-short">+ Анкета</span>
                <span className="header__cta-icon" aria-hidden="true">+</span>
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="container">
        <div className="hero">
          <h2 className="hero__title">
            Соседи, с которыми <span className="accent">по пути</span>
          </h2>
          <p className="hero__sub">
            Кампус-отель «{CAMPUS[campus]}» · комнаты на{" "}
            {campusRoomsText(campus)} человека · только{" "}
            {GENDER_WORD[gender].toLowerCase()}
          </p>
        </div>

        {/* Без анкеты человека не видно и он не может ничего сделать, а кнопку
            в шапке замечали не с первого раза — зовём крупно и по делу. */}
        {!loadingMe && !myProfile && (
          <div className="promo">
            <div className="promo__text">
              <strong className="promo__title">Тебя ещё никто не видит</strong>
              <span className="promo__sub">
                Размести анкету — иначе не получится ни написать, ни собрать
                компанию. Это минута.
              </span>
            </div>
            <button className="promo__btn" onClick={() => setModal("create")}>
              Разместить анкету
            </button>
          </div>
        )}

        <div className="tabs">
          <button
            className={`tabs__btn${tab === "singles" ? " tabs__btn--on" : ""}`}
            onClick={() => setTab("singles")}
          >
            Ищут соседей
            <span className="tabs__badge">{profiles.length}</span>
          </button>
          <button
            className={`tabs__btn${tab === "groups" ? " tabs__btn--on" : ""}`}
            onClick={() => setTab("groups")}
          >
            Компании
            <span className="tabs__badge">{groups.length}</span>
          </button>
        </div>

        {incomingInvites.length > 0 && (
          <div className="invites">
            {incomingInvites.map((inv) => (
              <div className="invite" key={inv.id}>
                <span className="invite__text">
                  🤝 <strong>{inv.from_profile.name}</strong> зовёт жить вместе —
                  комната на {inv.capacity}
                </span>
                <div className="invite__actions">
                  <button
                    className="invite__yes"
                    onClick={() => handleRespondInvite(inv.id, true)}
                    disabled={busy}
                  >
                    Согласиться
                  </button>
                  <button
                    className="invite__no"
                    onClick={() => handleRespondInvite(inv.id, false)}
                    disabled={busy}
                  >
                    Отказаться
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {tab === "singles" && (
          <Filters
            filters={filters}
            campus={campus}
            onChange={setFilters}
            onReset={() => setFilters(EMPTY_FILTERS)}
          />
        )}

        {loading && <p className="state">Загрузка…</p>}
        {error && <p className="state state--error">{error}</p>}

        {!loading && !error && tab === "singles" && (
          <>
            <p className="count">
              Ищут соседей: <strong>{profiles.length}</strong>
              {openGroups.length > 0 && (
                <>
                  {" "}· компаний с местами: <strong>{openGroups.length}</strong>
                </>
              )}
            </p>
            {profiles.length === 0 ? (
              <p className="state">
                {filtersActive
                  ? "Под фильтры никто не подошёл. Попробуй смягчить условия."
                  : "Пока здесь пусто. Размести анкету первым — и тебя увидят."}
              </p>
            ) : (
              <div className="grid">
                {profiles.map((p) => (
                  <RoommateCard
                    key={p.id}
                    profile={p}
                    myProfile={myProfile}
                    capacities={capacities}
                    invite={myInvites.find(
                      (i) =>
                        i.to_profile_id === p.id &&
                        i.from_profile_id === myProfile?.id
                    )}
                    onInvite={handleInvite}
                    busy={busy}
                  />
                ))}
              </div>
            )}
          </>
        )}

        {!loading && !error && tab === "groups" && (
          <>
            <div className="groups__top">
              <p className="count">
                Компаний: <strong>{groups.length}</strong> · с местами:{" "}
                <strong>{openGroups.length}</strong>
              </p>
              {canStartGroup && (
                <div className="groups__new">
                  <span>Договорились с кем-то? Создай компанию:</span>
                  {capacities.map((capacity) => (
                    <button
                      key={capacity}
                      className="groups__new-btn"
                      onClick={() => handleCreateGroup(capacity)}
                      disabled={busy}
                    >
                      на {capacity}
                    </button>
                  ))}
                </div>
              )}
              {!myProfile && (
                <p className="groups__hint">
                  Размести анкету — и сможешь создать свою компанию или вступить
                  в чужую.
                </p>
              )}
            </div>

            {groups.length === 0 ? (
              <p className="state">
                Пока никто не собрался. Создай первую компанию — остальные
                присоединятся.
              </p>
            ) : (
              <div className="grid grid--groups">
                {groups.map((g) => (
                  <GroupCard
                    key={g.id}
                    group={g}
                    myProfile={myProfile}
                    requests={incoming.filter((r) => r.group_id === g.id)}
                    myRequestHere={myRequests.find((r) => r.group_id === g.id)}
                    onRequest={handleRequest}
                    onCancelRequest={handleCancelRequest}
                    onVote={handleVote}
                    onLeave={handleLeave}
                    onChangeCapacity={handleChangeCapacity}
                    capacities={capacities}
                    busy={busy}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </main>

      <footer className="footer">
        Кампус-отели Диск и Облако · сервис поиска соседей по комнате
      </footer>

      {modal === "admin" && <AdminPanel onClose={() => setModal(null)} />}

      {(modal === "create" || modal === "edit") && (
        <AddProfileModal
          gender={gender}
          campus={campus}
          profile={modal === "edit" ? myProfile : null}
          onClose={() => setModal(null)}
          onCreated={handleCreated}
          onUpdated={handleUpdated}
          onDeleted={handleDeleted}
        />
      )}
    </div>
  );
}
