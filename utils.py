from telegram import InlineKeyboardMarkup, LinkPreviewOptions
from config import FACULTIES, STUDY_FORMS
from database import get_profile

_NO_PREVIEW = LinkPreviewOptions(is_disabled=True)


def profile_info(user_id: int) -> str:
    profile = get_profile(user_id)
    if not profile:
        return "👤 *Профиль не настроен*\nНажмите «Настроить профиль»."
    fac_name  = FACULTIES.get(profile["faculty"], profile["faculty"])
    form_name = STUDY_FORMS.get(profile["form"],   profile["form"])
    return (
        f"👤 *Ваш профиль:*\n"
        f"🏛️ {fac_name}\n"
        f"📋 {form_name}\n"
        f"👥 Группа: *{profile['grp']}*"
    )


async def send_long(
    message_obj,
    text: str,
    parse_mode: str = "Markdown",
    reply_markup: InlineKeyboardMarkup | None = None,
):
    """
    Отправляет текст чанками по 4000 символов.
    Если передан reply_markup — он прикрепляется к последнему чанку.
    """
    chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)]
    for idx, chunk in enumerate(chunks):
        is_last = (idx == len(chunks) - 1)
        await message_obj.reply_text(
            chunk,
            parse_mode=parse_mode,
            link_preview_options=_NO_PREVIEW,
            reply_markup=reply_markup if is_last else None,
        )
