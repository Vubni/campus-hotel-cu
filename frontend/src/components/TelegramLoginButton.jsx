import { useEffect, useRef } from "react";

let callbackSeq = 0;

/**
 * Telegram Login Widget. Скрипт сам рисует кнопку внутри контейнера и зовёт
 * глобальную функцию из data-onauth, поэтому колбэк вешаем на window.
 *
 * Важно: виджет работает только на домене, указанном боту в @BotFather
 * (команда /setdomain). На localhost Telegram кнопку не покажет.
 */
export default function TelegramLoginButton({ botUsername, onAuth, onError }) {
  const container = useRef(null);
  const onAuthRef = useRef(onAuth);
  onAuthRef.current = onAuth;

  useEffect(() => {
    if (!botUsername || !container.current) return;

    const callbackName = `onTelegramAuth_${++callbackSeq}`;
    window[callbackName] = (user) => onAuthRef.current?.(user);

    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.async = true;
    script.setAttribute("data-telegram-login", botUsername);
    script.setAttribute("data-size", "large");
    script.setAttribute("data-radius", "20");
    script.setAttribute("data-userpic", "true");
    script.setAttribute("data-request-access", "write");
    script.setAttribute("data-onauth", `${callbackName}(user)`);
    script.onerror = () =>
      onError?.("Не удалось загрузить виджет Telegram — проверь соединение");

    const node = container.current;
    node.appendChild(script);

    return () => {
      delete window[callbackName];
      node.innerHTML = "";
    };
  }, [botUsername, onError]);

  return <div className="tg-login" ref={container} />;
}
