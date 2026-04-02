from config import FACULTIES, STUDY_FORMS
from database import get_profile


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


async def send_long(message_obj, text: str, parse_mode: str = "Markdown"):
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        await message_obj.reply_text(
            chunk, parse_mode=parse_mode, disable_web_page_preview=True
        )
