import { getInitData } from "./telegram.js";

const BASE = "/api";

/**
 * Подпись Telegram в каждом запросе.
 *
 * Это и есть авторизация: initData подписан токеном бота, подделать его
 * нельзя, и сервер по нему понимает, кто именно действует. Пусто (обычный
 * браузер) — сервер ответит 401, если у него настроен токен бота.
 */
function authHeaders(extra = {}) {
  const initData = getInitData();
  return initData ? { ...extra, "X-Telegram-Init-Data": initData } : { ...extra };
}

const JSON_HEADERS = () => authHeaders({ "Content-Type": "application/json" });


export async function fetchProfiles(filters = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== "" && value !== null && value !== undefined) {
      params.append(key, value);
    }
  }
  const qs = params.toString();
  const res = await fetch(`${BASE}/profiles${qs ? `?${qs}` : ""}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Не удалось загрузить профили");
  return res.json();
}

async function jsonOrThrow(res, fallback) {
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || fallback);
  }
  return res.status === 204 ? null : res.json();
}

export async function fetchGroups(filters = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== "" && value !== null && value !== undefined) {
      params.append(key, value);
    }
  }
  const qs = params.toString();
  const res = await fetch(`${BASE}/groups${qs ? `?${qs}` : ""}`, {
    headers: authHeaders(),
  });
  return jsonOrThrow(res, "Не удалось загрузить компании");
}

export async function createGroup(capacity, profileId) {
  const res = await fetch(`${BASE}/groups`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify({ capacity, profile_id: profileId }),
  });
  return jsonOrThrow(res, "Не удалось создать компанию");
}

// Вступить напрямую нельзя — только подать заявку, её подтверждают жильцы.
export async function requestJoin(groupId, profileId) {
  const res = await fetch(`${BASE}/groups/${groupId}/requests`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify({ profile_id: profileId }),
  });
  return jsonOrThrow(res, "Не удалось отправить заявку");
}

export async function fetchGroupRequests(groupId) {
  const res = await fetch(`${BASE}/groups/${groupId}/requests?status=pending`, { headers: authHeaders() });
  return jsonOrThrow(res, "Не удалось загрузить заявки");
}

export async function fetchMyRequests(profileId) {
  const res = await fetch(`${BASE}/profiles/${profileId}/requests?status=pending`, { headers: authHeaders() });
  return jsonOrThrow(res, "Не удалось загрузить заявки");
}

export async function voteRequest(requestId, profileId, approve) {
  const res = await fetch(`${BASE}/requests/${requestId}/vote`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify({ profile_id: profileId, approve }),
  });
  return jsonOrThrow(res, "Не удалось проголосовать");
}

export async function cancelRequest(requestId, profileId) {
  const res = await fetch(`${BASE}/requests/${requestId}/cancel`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify({ profile_id: profileId }),
  });
  return jsonOrThrow(res, "Не удалось отменить заявку");
}

/**
 * Сузить или расширить уже созданную комнату.
 * Меняет любой жилец; меньше числа участников сервер не даст.
 */
export async function changeGroupCapacity(groupId, profileId, capacity) {
  const res = await fetch(`${BASE}/groups/${groupId}/capacity`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify({ profile_id: profileId, capacity }),
  });
  return jsonOrThrow(res, "Не удалось изменить размер комнаты");
}

export async function leaveGroup(groupId, profileId) {
  const res = await fetch(`${BASE}/groups/${groupId}/leave`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify({ profile_id: profileId }),
  });
  return jsonOrThrow(res, "Не удалось выйти из компании");
}

/**
 * Аватарки из профиля Telegram — порциями, чтобы форма открывалась быстро.
 * Возвращает { photos, total }: по total видно, есть ли что догружать.
 */
export async function fetchTelegramPhotos(initData, offset = 0, limit = 6) {
  const res = await fetch(`${BASE}/telegram/photos`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify({ init_data: initData, offset, limit }),
  });
  return jsonOrThrow(res, "Не удалось получить аватарки из Telegram");
}

/** Найти свою анкету по подписи Telegram — не полагаясь на localStorage. */
export async function fetchMyProfileByTelegram(initData) {
  const res = await fetch(`${BASE}/profiles/me`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify({ init_data: initData }),
  });
  return jsonOrThrow(res, "Анкета не найдена");
}

// «Давай жить вместе» — комната создаётся только после согласия приглашённого.
export async function createInvite(fromProfileId, toProfileId, capacity) {
  const res = await fetch(`${BASE}/invites`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify({
      from_profile_id: fromProfileId,
      to_profile_id: toProfileId,
      capacity,
    }),
  });
  return jsonOrThrow(res, "Не удалось отправить приглашение");
}

export async function fetchMyInvites(profileId) {
  const res = await fetch(`${BASE}/profiles/${profileId}/invites?status=pending`, { headers: authHeaders() });
  return jsonOrThrow(res, "Не удалось загрузить приглашения");
}

export async function respondInvite(inviteId, profileId, accept) {
  const res = await fetch(`${BASE}/invites/${inviteId}/respond`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify({ profile_id: profileId, accept }),
  });
  return jsonOrThrow(res, "Не удалось ответить на приглашение");
}

export async function fetchProfile(id) {
  const res = await fetch(`${BASE}/profiles/${id}`, { headers: authHeaders() });
  return jsonOrThrow(res, "Анкета не найдена");
}

/** Сводка для админки: сколько анкет, у скольких есть ник и бот. */
export async function fetchAdminStats() {
  const res = await fetch(`${BASE}/admin/stats`, { headers: authHeaders() });
  return jsonOrThrow(res, "Не удалось загрузить статистику");
}

/**
 * Просим бота прислать выгрузку файлом в чат.
 *
 * Не скачиваем в браузере: внутри Telegram на macOS и iOS скачанный файл
 * открыть нечем — таблица показывается пустой или не открывается вовсе.
 * Присланный ботом документ система открывает сама.
 */
export async function sendExport({ format, scope, campus }) {
  const res = await fetch(`${BASE}/admin/export/send`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify({ format, scope, campus: campus || null }),
  });
  const data = await jsonOrThrow(res, "Не удалось отправить выгрузку");
  return data.filename;
}

export async function fetchConfig() {
  const res = await fetch(`${BASE}/config`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Не удалось загрузить настройки");
  return res.json();
}

export async function uploadPhoto(file) {
  const body = new FormData();
  body.append("file", file);
  const res = await fetch(`${BASE}/uploads/photo`, {
    method: "POST",
    headers: authHeaders(),
    body,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Не удалось загрузить фото");
  }
  return res.json();
}

// Вход через Telegram Login Widget (обычный веб)
export async function authTelegram(widgetUser) {
  const res = await fetch(`${BASE}/auth/telegram`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify(widgetUser),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Telegram не подтвердил вход");
  }
  return res.json();
}

// Вход из Telegram Mini App (сайт открыт внутри Telegram)
export async function authTelegramWebApp(initData) {
  const res = await fetch(`${BASE}/auth/telegram/webapp`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify({ init_data: initData }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Telegram не подтвердил вход");
  }
  return res.json();
}

export async function createProfile(profile) {
  const res = await fetch(`${BASE}/profiles`, {
    method: "POST",
    headers: JSON_HEADERS(),
    body: JSON.stringify(profile),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Не удалось создать профиль");
  }
  return res.json();
}

export async function updateProfile(id, profile) {
  const res = await fetch(`${BASE}/profiles/${id}`, {
    method: "PUT",
    headers: JSON_HEADERS(),
    body: JSON.stringify(profile),
  });
  return jsonOrThrow(res, "Не удалось сохранить анкету");
}

export async function deleteProfile(id) {
  const res = await fetch(`${BASE}/profiles/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  return jsonOrThrow(res, "Не удалось удалить анкету");
}
