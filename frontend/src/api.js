const BASE = "/api";

export async function fetchProfiles(filters = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== "" && value !== null && value !== undefined) {
      params.append(key, value);
    }
  }
  const qs = params.toString();
  const res = await fetch(`${BASE}/profiles${qs ? `?${qs}` : ""}`);
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
  const res = await fetch(`${BASE}/groups${qs ? `?${qs}` : ""}`);
  return jsonOrThrow(res, "Не удалось загрузить компании");
}

export async function createGroup(capacity, profileId) {
  const res = await fetch(`${BASE}/groups`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ capacity, profile_id: profileId }),
  });
  return jsonOrThrow(res, "Не удалось создать компанию");
}

// Вступить напрямую нельзя — только подать заявку, её подтверждают жильцы.
export async function requestJoin(groupId, profileId) {
  const res = await fetch(`${BASE}/groups/${groupId}/requests`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_id: profileId }),
  });
  return jsonOrThrow(res, "Не удалось отправить заявку");
}

export async function fetchGroupRequests(groupId) {
  const res = await fetch(`${BASE}/groups/${groupId}/requests?status=pending`);
  return jsonOrThrow(res, "Не удалось загрузить заявки");
}

export async function fetchMyRequests(profileId) {
  const res = await fetch(`${BASE}/profiles/${profileId}/requests?status=pending`);
  return jsonOrThrow(res, "Не удалось загрузить заявки");
}

export async function voteRequest(requestId, profileId, approve) {
  const res = await fetch(`${BASE}/requests/${requestId}/vote`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_id: profileId, approve }),
  });
  return jsonOrThrow(res, "Не удалось проголосовать");
}

export async function cancelRequest(requestId, profileId) {
  const res = await fetch(`${BASE}/requests/${requestId}/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_id: profileId }),
  });
  return jsonOrThrow(res, "Не удалось отменить заявку");
}

export async function leaveGroup(groupId, profileId) {
  const res = await fetch(`${BASE}/groups/${groupId}/leave`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_id: profileId }),
  });
  return jsonOrThrow(res, "Не удалось выйти из компании");
}

export async function fetchProfile(id) {
  const res = await fetch(`${BASE}/profiles/${id}`);
  return jsonOrThrow(res, "Анкета не найдена");
}

export async function fetchConfig() {
  const res = await fetch(`${BASE}/config`);
  if (!res.ok) throw new Error("Не удалось загрузить настройки");
  return res.json();
}

export async function uploadPhoto(file) {
  const body = new FormData();
  body.append("file", file);
  const res = await fetch(`${BASE}/uploads/photo`, { method: "POST", body });
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
    headers: { "Content-Type": "application/json" },
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
    headers: { "Content-Type": "application/json" },
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
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Не удалось создать профиль");
  }
  return res.json();
}
