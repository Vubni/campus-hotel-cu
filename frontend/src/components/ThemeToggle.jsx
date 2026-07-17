import { useTheme } from "../useTheme.js";

const ICON = { system: "🌗", light: "☀️", dark: "🌙" };
const LABEL = { system: "Системная", light: "Светлая", dark: "Тёмная" };

export default function ThemeToggle({ compact = false }) {
  const { mode, cycle } = useTheme();
  return (
    <button
      className="theme-toggle"
      onClick={cycle}
      title={`Тема: ${LABEL[mode]} — нажми, чтобы сменить`}
      aria-label={`Тема: ${LABEL[mode]}`}
    >
      <span className="theme-toggle__icon">{ICON[mode]}</span>
      {!compact && <span className="theme-toggle__label">{LABEL[mode]}</span>}
    </button>
  );
}
