import { useEffect, useState } from "react";
import { downloadExport, fetchAdminStats } from "../api.js";
import { CAMPUS } from "../labels.js";

// Что кладём в каждый формат — подписи честно объясняют, что человек получит.
const FORMATS = [
  ["xlsx", "Excel (.xlsx)", "Два листа: пользователи и комнаты"],
  ["csv", "CSV (.zip)", "Два файла: users.csv и rooms.csv"],
  ["json", "JSON", "Для обработки программой"],
];

const SCOPES = [
  ["full", "Со всеми параметрами", "Анкеты целиком: быт, курс, направление"],
  ["short", "Только имена и ники", "Чтобы просто со всеми связаться"],
];

export default function AdminPanel({ onClose }) {
  const [stats, setStats] = useState(null);
  const [scope, setScope] = useState("full");
  const [campus, setCampus] = useState(""); // "" — оба кампус-отеля
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState("");

  useEffect(() => {
    fetchAdminStats()
      .then(setStats)
      .catch((err) => setError(err.message));
  }, []);

  async function handleDownload(format) {
    setBusy(format);
    setError("");
    setDone("");
    try {
      const filename = await downloadExport({ format, scope, campus });
      setDone(`Готово: ${filename}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="modal__overlay" onClick={onClose}>
      <div className="modal modal--admin" onClick={(e) => e.stopPropagation()}>
        <div className="modal__head">
          <h2>Админка</h2>
          <button className="modal__close" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="modal__form">
          {stats && (
            <div className="admin__stats">
              <div className="admin__stat">
                <b>{stats.profiles}</b>
                <span>анкет</span>
              </div>
              <div className="admin__stat">
                <b>{stats.with_username}</b>
                <span>с ником</span>
              </div>
              <div className="admin__stat">
                <b>{stats.with_bot}</b>
                <span>подключили бота</span>
              </div>
              <div className="admin__stat">
                <b>{stats.groups}</b>
                <span>комнат</span>
              </div>
              <div className="admin__stat">
                <b>{stats.in_groups}</b>
                <span>живут в комнатах</span>
              </div>
              {Object.entries(stats.by_campus).map(([name, count]) => (
                <div className="admin__stat" key={name}>
                  <b>{count}</b>
                  <span>{name}</span>
                </div>
              ))}
            </div>
          )}

          <div className="field">
            <span>Что выгружаем</span>
            <div className="admin__choices">
              {SCOPES.map(([value, label, hint]) => (
                <button
                  key={value}
                  type="button"
                  className={`admin__choice${
                    scope === value ? " admin__choice--on" : ""
                  }`}
                  onClick={() => setScope(value)}
                  aria-pressed={scope === value}
                >
                  <b>{label}</b>
                  <span>{hint}</span>
                </button>
              ))}
            </div>
          </div>

          <label className="field">
            <span>Кампус-отель</span>
            <select value={campus} onChange={(e) => setCampus(e.target.value)}>
              <option value="">Оба</option>
              {Object.entries(CAMPUS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>

          <div className="field">
            <span>Формат</span>
            <div className="admin__choices">
              {FORMATS.map(([value, label, hint]) => (
                <button
                  key={value}
                  type="button"
                  className="admin__choice admin__choice--action"
                  onClick={() => handleDownload(value)}
                  disabled={Boolean(busy)}
                >
                  <b>{busy === value ? "Готовим…" : label}</b>
                  <span>{hint}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Ники есть не у всех: часть людей их скрывает или не заводила.
              Честно предупреждаем, а не делаем вид, что выгрузка полная. */}
          {stats && stats.with_username < stats.profiles && (
            <p className="admin__note">
              У {stats.profiles - stats.with_username} из {stats.profiles} ник
              неизвестен — при выгрузке попробуем достать его из Telegram.
              Получится не для всех: ник виден боту, только если человек ему
              писал.
            </p>
          )}

          {done && <p className="admin__done">✓ {done}</p>}
          {error && <p className="modal__error">{error}</p>}
        </div>
      </div>
    </div>
  );
}
