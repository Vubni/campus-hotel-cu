import { useEffect } from "react";
import { setVerticalSwipes } from "./telegram.js";

/**
 * Пока открыта модалка — держим её неподвижно.
 *
 * Само по себе `position: fixed` у подложки телефон не убеждает: за ней
 * продолжает скроллиться страница, а внутри Telegram вертикальный свайп ещё и
 * тащит вниз весь мини-апп. Получается, что окно «шатается» и сквозь него
 * видно ленту. Поэтому фиксируем сразу три вещи:
 *
 *   1. body — position: fixed со сдвигом на текущую прокрутку. Только так iOS
 *      Safari перестаёт скроллить фон (одного overflow: hidden ему мало);
 *      сдвиг нужен, чтобы страница не прыгнула в начало при закрытии.
 *   2. свайп-закрытие мини-аппа — выключаем на время (Bot API 7.7).
 *   3. прокрутку возвращаем ровно туда, где человек был.
 */
export function useModalLock(active = true) {
  useEffect(() => {
    if (!active) return undefined;

    const { body } = document;
    const scrollY = window.scrollY;
    const saved = {
      position: body.style.position,
      top: body.style.top,
      left: body.style.left,
      right: body.style.right,
      width: body.style.width,
      overflow: body.style.overflow,
    };

    body.style.position = "fixed";
    body.style.top = `-${scrollY}px`;
    body.style.left = "0";
    body.style.right = "0";
    body.style.width = "100%";
    body.style.overflow = "hidden";
    setVerticalSwipes(false);

    return () => {
      Object.assign(body.style, saved);
      setVerticalSwipes(true);
      // Возвращаем прокрутку мгновенно: плавная анимация здесь выглядит как
      // самопроизвольный «отъезд» страницы после закрытия окна.
      window.scrollTo({ top: scrollY, behavior: "instant" });
    };
  }, [active]);
}
