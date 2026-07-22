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
    // Цвета шапки/фона под тему — только если клиент их поддерживает. На старых
    // версиях (6.0) эти методы не работают и Telegram сыплет предупреждениями.
    // Свайп-закрытие НЕ трогаем: его отключение мешало закрывать мини-апп.
    if (wa.isVersionAtLeast && wa.isVersionAtLeast("6.1")) {
      wa.setHeaderColor?.("bg_color");
      wa.setBackgroundColor?.("bg_color");
    }
  } catch {
    // Внутри обычного браузера этих методов может не быть — не мешаем работе.
  }
}

/**
 * Свернуть мини-апп. Нужно после того, как бот прислал файл: человек должен
 * оказаться в чате и увидеть, что файл пришёл.
 * Возвращает false, если свернуть нечего (обычный браузер).
 */
export function closeWebApp() {
  const wa = getWebApp();
  if (!wa?.close) return false;
  try {
    wa.close();
    return true;
  } catch {
    return false;
  }
}

/**
 * Параметр из ссылки t.me/<бот>?startapp=<это>. Так из общей ленты попадают
 * сразу на нужную анкету. Вне Telegram читаем его же из адреса: ?profile=123.
 */
export function getStartParam() {
  const fromTelegram = getWebApp()?.initDataUnsafe?.start_param;
  if (fromTelegram) return String(fromTelegram);
  const fromUrl = new URLSearchParams(window.location.search).get("profile");
  return fromUrl ? `p${fromUrl}` : "";
}

/**
 * Вертикальный свайп по мини-аппу: им Telegram сворачивает окно. Пока открыта
 * модалка, это мешает — форму «стаскивает» вниз вместе со всем приложением,
 * и из-под неё видно ленту. Метод появился в Bot API 7.7, на старых клиентах
 * его просто нет.
 */
export function setVerticalSwipes(enabled) {
  const wa = getWebApp();
  if (!wa) return;
  try {
    if (enabled) wa.enableVerticalSwipes?.();
    else wa.disableVerticalSwipes?.();
  } catch {
    // Старый клиент — молча живём без этого.
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
