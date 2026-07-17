import io
import uuid

from PIL import Image, UnidentifiedImageError

from config import UPLOAD_DIR

MAX_SIDE = 800  # px по большей стороне
PUBLIC_PREFIX = "/api/media"


class InvalidImage(Exception):
    pass


def save_image(raw: bytes) -> str:
    """Проверяет, что это картинка, ужимает и сохраняет как JPEG.

    Возвращает публичный URL вида /api/media/<uuid>.jpg
    """
    try:
        # verify() «расходует» файл, поэтому потом открываем заново.
        Image.open(io.BytesIO(raw)).verify()
        img = Image.open(io.BytesIO(raw))
    except (UnidentifiedImageError, OSError):
        raise InvalidImage("Файл не похож на изображение")

    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.jpg"
    img.save(UPLOAD_DIR / name, format="JPEG", quality=85, optimize=True)
    return f"{PUBLIC_PREFIX}/{name}"
