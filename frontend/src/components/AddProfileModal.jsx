import { useEffect, useState } from "react";
import { authTelegram, authTelegramWebApp, createProfile, fetchConfig } from "../api.js";
import { getInitData, isInsideTelegram } from "../telegram.js";
import { TRACK_OPTIONS } from "../labels.js";
import PhotoPicker from "./PhotoPicker.jsx";
import TelegramLoginButton from "./TelegramLoginButton.jsx";

const GENDER_WORD = { male: "Парень", female: "Девушка" };

export default function AddProfileModal({ gender, onClose, onCreated }) {
  const [config, setConfig] = useState(null);
  // Подтверждённые данные Telegram: их же отправим на сервер для перепроверки.
  const [tgAuth, setTgAuth] = useState(null);
  const [tgBusy, setTgBusy] = useState(false);
  const insideTelegram = isInsideTelegram();

  const [form, setForm] = useState({
    name: "",
    gender: gender,
    photo_url: "",
    telegram: "",
    track: "undecided",
    bio: "",
    room_capacity: 2,
    sleep_schedule: "any",
    smoking: "no",
    cleanliness: 3,
  });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  useEffect(() => {
    fetchConfig().then(setConfig).catch(() => setConfig(null));
  }, []);

  /** Подставляем имя, ник и аватар из подтверждённых данных Telegram. */
  function applyTelegramProfile(profile) {
    setForm((prev) => ({
      ...prev,
      name: profile.name || prev.name,
      telegram: profile.telegram || prev.telegram,
      photo_url: profile.photo_url || prev.photo_url,
    }));
  }

  async function handleWidgetAuth(user) {
    setError("");
    setTgBusy(true);
    try {
      const profile = await authTelegram(user);
      applyTelegramProfile(profile);
      setTgAuth({ telegram_auth: user });
    } catch (err) {
      setError(err.message);
    } finally {
      setTgBusy(false);
    }
  }

  async function handleWebAppAuth() {
    setError("");
    setTgBusy(true);
    try {
      const initData = getInitData();
      const profile = await authTelegramWebApp(initData);
      applyTelegramProfile(profile);
      setTgAuth({ telegram_init_data: initData });
    } catch (err) {
      setError(err.message);
    } finally {
      setTgBusy(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const payload = {
        ...form,
        // "" — «не предпочтительно»: шлём null, иначе Number("") даст 0.
        room_capacity:
          form.room_capacity === "" ? null : Number(form.room_capacity),
        cleanliness: Number(form.cleanliness),
        // Сервер перепроверит подпись и сам решит, ставить ли галочку.
        ...(tgAuth || {}),
      };
      const created = await createProfile(payload);
      onCreated(created);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal__overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal__head">
          <h2>Разместить анкету</h2>
          <button className="modal__close" onClick={onClose}>
            ×
          </button>
        </div>

        <form className="modal__form" onSubmit={handleSubmit}>
          <div className="field-row">
            <label className="field">
              <span>Имя *</span>
              <input required value={form.name} onChange={set("name")} maxLength={80} />
            </label>
            <label className="field field--sm">
              <span>Пол</span>
              <input value={GENDER_WORD[gender] || "—"} disabled readOnly />
            </label>
          </div>

          <label className="field">
            <span>Telegram * (без @)</span>
            <input
              required
              value={form.telegram}
              onChange={set("telegram")}
              placeholder="username"
              disabled={Boolean(tgAuth)}
              readOnly={Boolean(tgAuth)}
            />
          </label>

          <div className="field">
            <span>Фото</span>
            <PhotoPicker
              value={form.photo_url}
              name={form.name}
              onChange={(url) => setForm((prev) => ({ ...prev, photo_url: url }))}
              onError={setError}
            />

            {tgAuth ? (
              <p className="tg-block__done">
                ✓ Telegram подтверждён{form.telegram ? ` — @${form.telegram}` : ""}
              </p>
            ) : insideTelegram ? (
              <button
                type="button"
                className="tg-block__btn"
                onClick={handleWebAppAuth}
                disabled={tgBusy}
              >
                {tgBusy ? "Подключаем…" : "Взять фото и ник из Telegram"}
              </button>
            ) : config?.telegram_enabled ? (
              <div className="tg-block">
                <p className="tg-block__hint">
                  Или подставь фото и ник из своего профиля Telegram:
                </p>
                <TelegramLoginButton
                  botUsername={config.telegram_bot_username}
                  onAuth={handleWidgetAuth}
                  onError={setError}
                />
              </div>
            ) : null}
          </div>

          <label className="field">
            <span>Направление</span>
            <select value={form.track} onChange={set("track")}>
              {TRACK_OPTIONS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>О себе</span>
            <textarea rows={3} value={form.bio} onChange={set("bio")} />
          </label>

          <div className="field-row">
            <label className="field">
              <span>Комната на</span>
              <select value={form.room_capacity} onChange={set("room_capacity")}>
                <option value="">Не предпочтительно</option>
                <option value={2}>2 человека</option>
                <option value={3}>3 человека</option>
                <option value={4}>4 человека</option>
              </select>
            </label>
            <label className="field">
              <span>Режим сна</span>
              <select value={form.sleep_schedule} onChange={set("sleep_schedule")}>
                <option value="any">Без разницы</option>
                <option value="lark">Жаворонок</option>
                <option value="owl">Сова</option>
              </select>
            </label>
          </div>

          <div className="field-row">
            <label className="field">
              <span>Курение</span>
              <select value={form.smoking} onChange={set("smoking")}>
                <option value="no">Не курю</option>
                <option value="yes">Курю</option>
                <option value="vape">Электронки</option>
              </select>
            </label>
            <div className="field">
              <span>Чистоплотность: {form.cleanliness}/5</span>
              <div className="rating">
                {[1, 2, 3, 4, 5].map((level) => (
                  <button
                    key={level}
                    type="button"
                    className={`rating__btn${
                      Number(form.cleanliness) === level ? " rating__btn--on" : ""
                    }`}
                    onClick={() => setForm((prev) => ({ ...prev, cleanliness: level }))}
                    aria-pressed={Number(form.cleanliness) === level}
                  >
                    {level}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {error && <p className="modal__error">{error}</p>}

          <button className="modal__submit" type="submit" disabled={saving}>
            {saving ? "Сохраняем…" : "Разместить анкету"}
          </button>
        </form>
      </div>
    </div>
  );
}
