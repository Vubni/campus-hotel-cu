// Работа с Telegram Mini App SDK (telegram-web-app.js).
// Вне Telegram window.Telegram.WebApp либо отсутствует, либо initData пустой.

export function getWebApp() {
  return window.Telegram?.WebApp || null;
}

/** Сайт реально открыт внутри Telegram? Пустой initData = обычный браузер. */
export function isInsideTelegram() {
  const wa = getWebApp();
  return Boolean(wa && wa.initData);
}

export function getInitData() {
  return getWebApp()?.initData || "";
}

/** Сообщаем Telegram, что интерфейс готов, и разворачиваем на весь экран. */
export function initWebApp() {
  const wa = getWebApp();
  if (!wa) return;
  try {
    wa.ready();
    wa.expand();
    // Вертикальный свайп закрывает мини-апп и мешает прокрутке ленты — гасим его.
    wa.disableVerticalSwipes?.();
    // Шапка и фон под цвет темы клиента, чтобы не было чужеродной полосы.
    wa.setHeaderColor?.("bg_color");
    wa.setBackgroundColor?.("bg_color");
  } catch {
    // Внутри обычного браузера этих методов может не быть — не мешаем работе.
  }
}

/** Тема Telegram: подстраиваем приложение под тему клиента. */
export function getTelegramColorScheme() {
  return getWebApp()?.colorScheme || null;
}

/** Открыть ссылку: внутри Telegram — его средствами, иначе обычной вкладкой. */
export function openTelegramLink(url) {
  const wa = getWebApp();
  if (wa?.openTelegramLink) {
    wa.openTelegramLink(url);
    return true;
  }
  return false;
}
