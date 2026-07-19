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

// Новая анкета начинается с «не выбрано»: пусть человек ответит сам, чем мы
// припишем ему привычки, о которых он не говорил.
const EMPTY_FORM = {
  name: "",
  photo_url: "",
  telegram: "",
  track: "",
  course: "",
  bio: "",
  room_capacity: "",
  sleep_schedule: "",
  smoking: "",
  tidiness: "",
  wakeup: "",
  cooking: [], // можно выбрать несколько; пустой список — не выбрано
  guests: "",
  shower: "",
  temperature: "",
  noise: "",
  alcohol: "",
};

const COOKING_CHOICES = [
  ["self", "Сам"],
  ["together", "Вместе"],
  ["delivery", "Доставка / кафе"],
];

// Лимит на длину «о себе»: чтобы текст всегда помещался в карточку целиком.
const BIO_MAX = 300;

/** Собираем форму из существующей анкеты (режим редактирования). */
function formFromProfile(profile) {
  const form = { ...EMPTY_FORM };
  for (const key of Object.keys(EMPTY_FORM)) {
    if (profile[key] !== undefined && profile[key] !== null) {
      form[key] = profile[key];
    }
  }
  // NULL на сервере = «не выбрано» — в селекте это пустая строка.
  form.room_capacity = profile.room_capacity ?? "";
  form.course = profile.course ?? "";
  // Готовка — всегда массив (на случай старых строковых данных).
  form.cooking = Array.isArray(profile.cooking)
    ? profile.cooking
    : [profile.cooking].filter(Boolean);
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

  // Готовка — множественный выбор. Снять можно всё: пустой список означает
  // «не выбрано», и характеристика просто не показывается в анкете.
  function toggleCooking(value) {
    setForm((prev) => {
      const has = prev.cooking.includes(value);
      const next = has
        ? prev.cooking.filter((c) => c !== value)
        : [...prev.cooking, value];
      return { ...prev, cooking: next };
    });
  }

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
        // "" — «не выбрано»: шлём null, иначе Number("") дал бы 0.
        room_capacity:
          form.room_capacity === "" ? null : Number(form.room_capacity),
        course: form.course === "" ? null : Number(form.course),
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
                <option value="">—</option>
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
              <option value="">Не выбрано</option>
              {TRACK_OPTIONS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>
              О себе <span className="field__count">{form.bio.length}/{BIO_MAX}</span>
            </span>
            <textarea
              rows={3}
              maxLength={BIO_MAX}
              value={form.bio}
              onChange={set("bio")}
            />
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
                <option value="">Не выбрано</option>
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
                <option value="">Не выбрано</option>
                <option value="no">Не курю</option>
                <option value="yes">Курю</option>
                <option value="vape">Электронки</option>
              </select>
            </label>
            <label className="field">
              <span>Аккуратность</span>
              <select value={form.tidiness} onChange={set("tidiness")}>
                <option value="">Не выбрано</option>
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
                <option value="">Не выбрано</option>
                <option value="alarm_one">Один будильник</option>
                <option value="alarm_many">Десять будильников</option>
                <option value="natural">Просыпаюсь сам</option>
              </select>
            </label>
            <label className="field">
              <span>Гости</span>
              <select value={form.guests} onChange={set("guests")}>
                <option value="">Не выбрано</option>
                <option value="often">Часто зову гостей</option>
                <option value="sometimes">Иногда</option>
                <option value="never">Не зову</option>
              </select>
            </label>
          </div>

          <div className="field-row">
            <label className="field">
              <span>Душ</span>
              <select value={form.shower} onChange={set("shower")}>
                <option value="">Не выбрано</option>
                <option value="any">Когда как</option>
                <option value="morning">Утром</option>
                <option value="evening">Вечером</option>
              </select>
            </label>
            <label className="field">
              <span>Температура в комнате</span>
              <select value={form.temperature} onChange={set("temperature")}>
                <option value="">Не выбрано</option>
                <option value="cool">Прохладно</option>
                <option value="medium">Нормально</option>
                <option value="warm">Тепло</option>
              </select>
            </label>
          </div>

          <div className="field-row">
            <label className="field">
              <span>Звук</span>
              <select value={form.noise} onChange={set("noise")}>
                <option value="">Не выбрано</option>
                <option value="quiet">Тишина</option>
                <option value="headphones">Слушаю в наушниках</option>
                <option value="loud">Музыка вслух</option>
              </select>
            </label>
            <label className="field">
              <span>Алкоголь</span>
              <select value={form.alcohol} onChange={set("alcohol")}>
                <option value="">Не выбрано</option>
                <option value="no">Не пью</option>
                <option value="sometimes">Иногда</option>
                <option value="often">Часто</option>
              </select>
            </label>
          </div>

          <div className="field">
            <span>Готовка (можно выбрать несколько)</span>
            <div className="multi">
              {COOKING_CHOICES.map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  className={`multi__btn${
                    form.cooking.includes(value) ? " multi__btn--on" : ""
                  }`}
                  onClick={() => toggleCooking(value)}
                  aria-pressed={form.cooking.includes(value)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

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
