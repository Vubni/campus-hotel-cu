import { useCallback, useEffect, useState } from "react";
import { fetchMyProfileByTelegram, fetchProfile } from "./api.js";
import { getInitData, isInsideTelegram } from "./telegram.js";

const KEY = "obshaga_my_profile_id";

/**
 * «Моя анкета».
 *
 * Внутри Telegram личность определяет подпись initData — это надёжно и
 * переживает смену устройства и очистку кэша. localStorage остаётся
 * запасным вариантом для обычного браузера, где подписи нет.
 */
export function useMyProfile() {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    // 1) Мини-апп: спрашиваем сервер «кто я» по подписи Telegram.
    if (isInsideTelegram()) {
      try {
        const mine = await fetchMyProfileByTelegram(getInitData());
        localStorage.setItem(KEY, String(mine.id));
        setProfile(mine);
        return mine;
      } catch {
        // 404 — анкеты действительно нет. Пробуем localStorage ниже:
        // анкету могли создать в браузере без входа через Telegram.
      } finally {
        setLoading(false);
      }
    }

    // 2) Обычный браузер (или анкета без привязки к Telegram).
    const id = localStorage.getItem(KEY);
    if (!id) {
      setProfile(null);
      setLoading(false);
      return null;
    }
    try {
      const fresh = await fetchProfile(id);
      setProfile(fresh);
      return fresh;
    } catch {
      // Анкету удалили или база пересоздана — забываем протухший id.
      localStorage.removeItem(KEY);
      setProfile(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const remember = useCallback((created) => {
    localStorage.setItem(KEY, String(created.id));
    setProfile(created);
  }, []);

  const forget = useCallback(() => {
    localStorage.removeItem(KEY);
    setProfile(null);
  }, []);

  return { myProfile: profile, loadingMe: loading, remember, forget, reloadMe: reload };
}
