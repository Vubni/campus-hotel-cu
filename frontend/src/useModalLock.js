import { useEffect } from "react";
import { setVerticalSwipes } from "./telegram.js";

// Пометка на <body>, что страницу держит открытая модалка. Нужна на случай,
// если снятие блокировки не отработало: по ней видно причину, и по ней же
// подстраховка ниже понимает, что чинить.
const FLAG = "data-modal-lock";

/** Возвращает страницу в обычное состояние. Безопасно звать сколько угодно раз. */
function unlock(body, saved, scrollY) {
  Object.assign(body.style, saved);
  body.removeAttribute(FLAG);
  // Двухаргументная форма, а не { behavior: … }: значение "instant" появилось
  // в Safari только к 15.4, а собираемся мы под Safari 14 — на старом WebView
  // это в лучшем случае игнорируется, в худшем роняет размонтирование.
  // Здесь же прокрутка и так нужна мгновенная.
  window.scrollTo(0, scrollY);
}

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
 *
 * Цена ошибки здесь несимметрична: не заблокировали — окно слегка шатается,
 * не разблокировали — страница НЕ ПРОКРУЧИВАЕТСЯ ВООБЩЕ и приложением нельзя
 * пользоваться. Поэтому снятие блокировки защищено со всех сторон.
 */
export function useModalLock(active = true) {
  useEffect(() => {
    if (!active) return undefined;

    const { body } = document;
    const scrollY = window.scrollY;
    // Если предыдущая блокировка почему-то не снялась, её значения уже лежат
    // в inline-стилях — принять их за «исходные» значило бы зафиксировать
    // страницу навсегда. В таком случае восстанавливаем чистое состояние.
    const stale = body.hasAttribute(FLAG);
    const saved = stale
      ? { position: "", top: "", left: "", right: "", width: "", overflow: "" }
      : {
          position: body.style.position,
          top: body.style.top,
          left: body.style.left,
          right: body.style.right,
          width: body.style.width,
          overflow: body.style.overflow,
        };

    body.setAttribute(FLAG, "");
    body.style.position = "fixed";
    body.style.top = `-${scrollY}px`;
    body.style.left = "0";
    body.style.right = "0";
    body.style.width = "100%";
    body.style.overflow = "hidden";
    setVerticalSwipes(false);

    // Последний рубеж: если размонтирование не случится (ошибка выше по дереву,
    // переход по ссылке), страница всё равно не останется пришпиленной.
    const rescue = () => unlock(body, saved, scrollY);
    window.addEventListener("pagehide", rescue);

    return () => {
      window.removeEventListener("pagehide", rescue);
      // Порядок важен: сначала отпускаем страницу, потом всё остальное.
      // Что бы ни случилось дальше, прокрутка уже работает.
      unlock(body, saved, scrollY);
      setVerticalSwipes(true);
    };
  }, [active]);
}
