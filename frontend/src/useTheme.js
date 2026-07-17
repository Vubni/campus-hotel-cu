import { useEffect, useState } from "react";

const KEY = "obshaga_theme";

// mode: "system" | "light" | "dark"
export function applyTheme(mode) {
  const dark =
    mode === "dark" ||
    (mode === "system" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
}

export function useTheme() {
  const [mode, setMode] = useState(() => localStorage.getItem(KEY) || "system");

  useEffect(() => {
    applyTheme(mode);
    localStorage.setItem(KEY, mode);

    if (mode === "system") {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      const handler = () => applyTheme("system");
      mq.addEventListener("change", handler);
      return () => mq.removeEventListener("change", handler);
    }
  }, [mode]);

  // system → light → dark → system
  const cycle = () =>
    setMode((m) => (m === "system" ? "light" : m === "light" ? "dark" : "system"));

  return { mode, cycle };
}
