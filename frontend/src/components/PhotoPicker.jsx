import { useRef, useState } from "react";
import { uploadPhoto } from "../api.js";

export default function PhotoPicker({ value, onChange, onError, name }) {
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState(false);

  async function handleFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    onError?.("");
    setUploading(true);
    try {
      const { photo_url } = await uploadPhoto(file);
      onChange(photo_url);
    } catch (err) {
      onError?.(err.message);
    } finally {
      setUploading(false);
      // Сбрасываем, чтобы повторный выбор того же файла тоже сработал.
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  const initial = (name || "?").trim().charAt(0).toUpperCase() || "?";

  return (
    <div className="photo-picker">
      <div className="photo-picker__preview">
        {value ? (
          <img src={value} alt="Фото профиля" />
        ) : (
          <span className="photo-picker__initial">{initial}</span>
        )}
      </div>

      <div className="photo-picker__actions">
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          hidden
          onChange={handleFile}
        />
        <button
          type="button"
          className="photo-picker__btn"
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
        >
          {uploading ? "Загружаем…" : value ? "Заменить фото" : "Загрузить фото"}
        </button>
        {value && (
          <button
            type="button"
            className="photo-picker__remove"
            onClick={() => onChange("")}
            disabled={uploading}
          >
            Удалить
          </button>
        )}
        <p className="photo-picker__hint">JPG или PNG, до 5 МБ</p>
      </div>
    </div>
  );
}
