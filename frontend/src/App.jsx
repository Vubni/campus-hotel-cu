import { useEffect, useState } from "react";
import {
  cancelRequest,
  createGroup,
  fetchGroupRequests,
  fetchGroups,
  fetchMyRequests,
  fetchProfiles,
  leaveGroup,
  requestJoin,
  voteRequest,
} from "./api.js";
import RoommateCard from "./components/RoommateCard.jsx";
import GroupCard from "./components/GroupCard.jsx";
import Filters from "./components/Filters.jsx";
import AddProfileModal from "./components/AddProfileModal.jsx";
import GenderGate from "./components/GenderGate.jsx";
import ThemeToggle from "./components/ThemeToggle.jsx";
import { initWebApp } from "./telegram.js";
import { useMyProfile } from "./useMyProfile.js";

const GENDER_KEY = "obshaga_gender";

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
  const [tab, setTab] = useState("singles"); // "singles" | "groups"

  const [profiles, setProfiles] = useState([]);
  const [groups, setGroups] = useState([]);
  // Заявки в мою комнату (id заявки → голосуем) и мои исходящие заявки.
  const [incoming, setIncoming] = useState([]);
  const [myRequests, setMyRequests] = useState([]);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [modal, setModal] = useState(null); // null | "create" | "edit"
  const [busy, setBusy] = useState(false);

  const { myProfile, remember, forget, reloadMe } = useMyProfile();

  function chooseGender(value) {
    localStorage.setItem(GENDER_KEY, value);
    setGender(value);
  }

  async function load(currentFilters, currentGender) {
    setLoading(true);
    setError("");
    try {
      // Одиночки — те, кто ещё не в компании; компании грузим отдельно.
      const [people, companies] = await Promise.all([
        fetchProfiles({
          ...currentFilters,
          gender: currentGender,
          without_group: true,
        }),
        fetchGroups({ gender: currentGender }),
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
      return;
    }
    try {
      const [mine, inbox] = await Promise.all([
        fetchMyRequests(me.id),
        me.group_id ? fetchGroupRequests(me.group_id) : Promise.resolve([]),
      ]);
      setMyRequests(mine);
      setIncoming(inbox);
    } catch {
      // Заявки — не критично: лента должна работать и без них.
      setIncoming([]);
    }
  }

  // Если сайт открыт внутри Telegram — разворачиваем окно Mini App.
  useEffect(() => {
    initWebApp();
  }, []);

  useEffect(() => {
    if (!gender) return;
    const id = setTimeout(() => load(filters, gender), 250);
    return () => clearTimeout(id);
  }, [filters, gender]);

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
    const [, me] = await Promise.all([load(filters, gender), reloadMe()]);
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

  if (!gender) {
    return <GenderGate onSelect={chooseGender} />;
  }

  const openGroups = groups.filter((g) => g.spots_left > 0);
  const canStartGroup = myProfile && !myProfile.group_id;
  // Пусто из-за фильтров или тут вообще никого нет — это разные сообщения.
  const filtersActive = Object.values(filters).some((v) => v !== "");

  return (
    <div className="app">
      <header className="header">
        <div className="header__inner">
          <div className="header__brand">
            <span className="header__logo">🏠</span>
            <div>
              <h1>Кампус-отель Диск</h1>
              <p>Найди соседа по комнате</p>
            </div>
          </div>

          <div className="header__right">
            <ThemeToggle compact />
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
            Комнаты на 2–4 человека · только {GENDER_WORD[gender].toLowerCase()}
          </p>
        </div>

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

        {tab === "singles" && (
          <Filters
            filters={filters}
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
                  <RoommateCard key={p.id} profile={p} />
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
                  {[2, 3, 4].map((capacity) => (
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
                    busy={busy}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </main>

      <footer className="footer">
        Кампус-отель Диск · сервис поиска соседей по комнате в общежитии
      </footer>

      {modal && (
        <AddProfileModal
          gender={gender}
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
