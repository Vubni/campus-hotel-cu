import { useCallback, useEffect, useState } from "react";
import { fetchProfile } from "./api.js";

const KEY = "obshaga_my_profile_id";

/**
 * «Моя анкета» — id запоминается в браузере после её создания.
 * Полноценной авторизации нет, поэтому это единственный способ понять,
 * от чьего имени вступать в компанию и выходить из неё.
 */
export function useMyProfile() {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
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
