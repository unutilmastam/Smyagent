"""Mustafo persona defaults (CLAUDE.md §5, ADR-0005). Pure.

These are the built-in defaults. M8 stores editable, versioned copies in
`persona_settings`; until then every client-facing text uses these.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Language(str, Enum):
    UZ = "uz"  # Uzbek, Latin script
    UZ_CYRL = "uz_cyrl"
    RU = "ru"
    EN = "en"


@dataclass(frozen=True)
class PersonaText:
    disclosure: str
    signature: str
    opt_out: str


SIGNATURE_FOOTER = "ITcoDe.Uz | itcode.uz | Telegram: @ITcoDe_Uz"

PERSONA: dict[Language, PersonaText] = {
    Language.UZ: PersonaText(
        disclosure=(
            "Assalomu alaykum! Men Mustafo — ITcoDe.Uz kompaniyasining SMY Agent AI yordamchisiman."
        ),
        signature=f"Mustafo — SMY Agent (AI yordamchi)\n{SIGNATURE_FOOTER}",
        opt_out=(
            'Agar bu sizga kerak bo\'lmasa, "kerak emas" deb javob yozing — '
            "boshqa bezovta qilmaymiz."
        ),
    ),
    Language.UZ_CYRL: PersonaText(
        disclosure=(
            "Ассалому алайкум! Мен Мустафо — ITcoDe.Uz компаниясининг SMY Agent AI ёрдамчисиман."
        ),
        signature=f"Мустафо — SMY Agent (AI ёрдамчи)\n{SIGNATURE_FOOTER}",
        opt_out=(
            'Агар бу сизга керак бўлмаса, "керак эмас" деб жавоб ёзинг — бошқа безовта қилмаймиз.'
        ),
    ),
    Language.RU: PersonaText(
        disclosure="Здравствуйте! Я Мустафо — AI-ассистент SMY Agent компании ITcoDe.Uz.",
        signature=f"Мустафо — SMY Agent (AI-ассистент)\n{SIGNATURE_FOOTER}",
        opt_out=(
            "Если вам это не нужно, ответьте «не пишите» — мы больше не будем вас беспокоить."
        ),
    ),
    Language.EN: PersonaText(
        disclosure="Hello! I'm Mustafo, the SMY Agent AI assistant at ITcoDe.Uz.",
        signature=f"Mustafo — SMY Agent (AI assistant)\n{SIGNATURE_FOOTER}",
        opt_out='If this is not relevant for you, reply "stop" and we will not write again.',
    ),
}

# Russian is the default client language in KZ / KG / TJ (CLAUDE.md §3).
_COUNTRY_LANGUAGE = {"UZ": Language.UZ, "KZ": Language.RU, "KG": Language.RU, "TJ": Language.RU}


def language_for_country(country: str) -> Language:
    return _COUNTRY_LANGUAGE.get(country.upper(), Language.EN)


def is_cyrillic(language: Language) -> bool:
    return language in (Language.RU, Language.UZ_CYRL)
