import { useEffect, useState } from "react";
import {
  authTelegram,
  authTelegramWebApp,
  createProfile,
  deleteProfile,
  fetchConfig,
  updateProfile,
} from "../api.js";
import { getInitData, isInsideTelegram } from "../telegram.js";
import { TRACK_OPTIONS } from "../labels.js";
import PhotoPicker from "./PhotoPicker.jsx";
import TelegramLoginButton from "./TelegramLoginButton.jsx";

const GENDER_WORD = { male: "Парень", female: "Девушка" };

// Значения по умолчанию для новой анкеты.
const EMPTY_FORM = {
  name: "",
  photo_url: "",
  telegram: "",
  track: "undecided",
  course: 1,
  bio: "",
  room_capacity: 2,
  sleep_schedule: "any",
  smoking: "no",
  tidiness: "medium",
  wakeup: "alarm_one",
  cooking: "self",
  guests: "sometimes",
};

/** Собираем форму из существующей анкеты (режим редактирования). */
function formFromProfile(profile) {
  const form = { ...EMPTY_FORM };
  for (const key of Object.keys(EMPTY_FORM)) {
    if (profile[key] !== undefined && profile[key] !== null) {
      form[key] = profile[key];
    }
  }
  // NULL на сервере = «не предпочтительно» — в селекте это пустая строка.
  form.room_capacity = profile.room_capacity ?? "";
  return form;
}

export default function AddProfileModal({
  gender,
  profile = null,
  onClose,
  onCreated,
  onUpdated,
  onDeleted,
}) {
  const isEdit = Boolean(profile);
  const [config, setConfig] = useState(null);
  // Подтверждённые данные Telegram: их же отправим на сервер для перепроверки.
  const [tgAuth, setTgAuth] = useState(null);
  const [tgBusy, setTgBusy] = useState(false);
  const insideTelegram = isInsideTelegram();

  const [form, setForm] = useState(() =>
    isEdit ? formFromProfile(profile) : { ...EMPTY_FORM }
  );
  // Анкета уже подтверждена через Telegram (в режиме редактирования).
  const [verified, setVerified] = useState(
    isEdit ? Boolean(profile.telegram_verified) : false
  );
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  useEffect(() => {
    fetchConfig().then(setConfig).catch(() => setConfig(null));
  }, []);

  /** Подставляем имя, ник и аватар из подтверждённых данных Telegram. */
  function applyTelegramProfile(profileData) {
    setForm((prev) => ({
      ...prev,
      name: prev.name || profileData.name || "",
      telegram: profileData.telegram || prev.telegram,
      photo_url: prev.photo_url || profileData.photo_url || "",
    }));
  }

  async function handleWidgetAuth(user) {
    setError("");
    setTgBusy(true);
    try {
      const authProfile = await authTelegram(user);
      applyTelegramProfile(authProfile);
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
      const authProfile = await authTelegramWebApp(initData);
      applyTelegramProfile(authProfile);
      setTgAuth({ telegram_init_data: initData });
    } catch (err) {
      setError(err.message);
    } finally {
      setTgBusy(false);
    }
  }

  // Внутри Telegram сразу подтягиваем ник и фото — без лишней кнопки.
  useEffect(() => {
    if (insideTelegram && !isEdit) {
      handleWebAppAuth();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const tgConfirmed = Boolean(tgAuth) || verified;

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const payload = {
        ...form,
        gender,
        // "" — «не предпочтительно»: шлём null, иначе Number("") даст 0.
        room_capacity:
          form.room_capacity === "" ? null : Number(form.room_capacity),
        course: Number(form.course),
        // Сервер перепроверит подпись и сам решит, ставить ли галочку.
        ...(tgAuth || {}),
      };
      if (isEdit) {
        const updated = await updateProfile(profile.id, payload);
        onUpdated(updated);
      } else {
        const created = await createProfile(payload);
        onCreated(created);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    setError("");
    setDeleting(true);
    try {
      await deleteProfile(profile.id);
      onDeleted();
    } catch (err) {
      setError(err.message);
      setDeleting(false);
    }
  }

  return (
    <div className="modal__overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal__head">
          <h2>{isEdit ? "Моя анкета" : "Разместить анкету"}</h2>
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
              <span>Курс</span>
              <select value={form.course} onChange={set("course")}>
                {[1, 2, 3, 4, 5, 6].map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
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
              disabled={tgConfirmed}
              readOnly={tgConfirmed}
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

            {tgConfirmed ? (
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
            <label className="field">
              <span>Аккуратность</span>
              <select value={form.tidiness} onChange={set("tidiness")}>
                <option value="relaxed">Расслабленно</option>
                <option value="medium">Умеренно</option>
                <option value="neat">Аккуратно</option>
              </select>
            </label>
          </div>

          <div className="field-row">
            <label className="field">
              <span>Подъём утром</span>
              <select value={form.wakeup} onChange={set("wakeup")}>
                <option value="alarm_one">Один будильник</option>
                <option value="alarm_many">Десять будильников</option>
                <option value="natural">Просыпаюсь сам</option>
              </select>
            </label>
            <label className="field">
              <span>Готовка</span>
              <select value={form.cooking} onChange={set("cooking")}>
                <option value="self">Готовлю сам</option>
                <option value="together">Готовим вместе</option>
                <option value="delivery">Доставка и кафе</option>
              </select>
            </label>
          </div>

          <label className="field">
            <span>Гости</span>
            <select value={form.guests} onChange={set("guests")}>
              <option value="often">Часто зову гостей</option>
              <option value="sometimes">Иногда</option>
              <option value="never">Не зову</option>
            </select>
          </label>

          {error && <p className="modal__error">{error}</p>}

          <button className="modal__submit" type="submit" disabled={saving || deleting}>
            {saving
              ? "Сохраняем…"
              : isEdit
                ? "Сохранить изменения"
                : "Разместить анкету"}
          </button>

          {isEdit &&
            (confirmDelete ? (
              <div className="modal__danger">
                <span>Удалить анкету? Отменить нельзя.</span>
                <div className="modal__danger-actions">
                  <button
                    type="button"
                    className="modal__danger-cancel"
                    onClick={() => setConfirmDelete(false)}
                    disabled={deleting}
                  >
                    Оставить
                  </button>
                  <button
                    type="button"
                    className="modal__danger-confirm"
                    onClick={handleDelete}
                    disabled={deleting}
                  >
                    {deleting ? "Удаляем…" : "Удалить"}
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                className="modal__delete"
                onClick={() => setConfirmDelete(true)}
                disabled={saving}
              >
                Удалить анкету
              </button>
            ))}
        </form>
      </div>
    </div>
  );
}
