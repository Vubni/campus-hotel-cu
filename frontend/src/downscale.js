// Сжатие фото перед отправкой.
//
// С телефона камера отдаёт 3–6 МБ. На мобильном исходящем канале это минуты
// ожидания — в логах попадались загрузки по 17 минут, которые никто не дождался
// и которые сервер закрывал как «client disconnected». При этом сервер всё
// равно ужимает картинку до 800px по большей стороне, то есть почти весь этот
// трафик выбрасывается. Уменьшаем заранее — тот же результат за секунды.

// Вдвое больше серверных 800px: запас на случай, если размер там поднимут,
// и никакой видимой потери качества после ужатия.
const MAX_SIDE = 1600;
const QUALITY = 0.85;

// Меньше этого ужимать нет смысла: выигрыш копеечный, а лишнее перекодирование
// портит картинку.
const SKIP_BELOW_BYTES = 300 * 1024;

/** Читает файл в картинку с учётом EXIF-поворота (иначе фото ложится набок). */
async function toBitmap(file) {
  if (window.createImageBitmap) {
    try {
      return await createImageBitmap(file, { imageOrientation: "from-image" });
    } catch {
      // Старый браузер не знает опцию — падаем в запасной путь ниже.
    }
  }
  // <img> современные браузеры сами разворачивают по EXIF.
  const url = URL.createObjectURL(file);
  try {
    return await new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("не удалось прочитать картинку"));
      img.src = url;
    });
  } finally {
    URL.revokeObjectURL(url);
  }
}

/**
 * Возвращает уменьшенный JPEG или исходный файл, если ужимать нечего или
 * не получилось. Никогда не бросает: не смогли сжать — отправим как есть,
 * это медленнее, но рабочее.
 */
export async function downscaleImage(file) {
  if (!file.type.startsWith("image/")) return file;
  if (file.size <= SKIP_BELOW_BYTES) return file;

  try {
    const src = await toBitmap(file);
    const w = src.width;
    const h = src.height;
    if (!w || !h) return file;

    const scale = Math.min(1, MAX_SIDE / Math.max(w, h));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(w * scale);
    canvas.height = Math.round(h * scale);
    const ctx = canvas.getContext("2d");
    if (!ctx) return file;
    ctx.drawImage(src, 0, 0, canvas.width, canvas.height);
    src.close?.();

    const blob = await new Promise((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", QUALITY)
    );
    // Бывает, что сжатие не помогает (уже сжатая мелкая картинка) — тогда
    // отправлять раздутую копию незачем.
    if (!blob || blob.size >= file.size) return file;

    return new File([blob], file.name.replace(/\.[^.]+$/, "") + ".jpg", {
      type: "image/jpeg",
      lastModified: Date.now(),
    });
  } catch {
    return file;
  }
}
