"""IME(특히 한글) 상태에서 키 입력을 정규화하기 위한 헬퍼 모듈."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from textual.binding import Binding

# 2-벌식 자판 기준 알파벳 ↔ 자모 매핑
_LATIN_TO_HANGUL = {
    "q": "ㅂ",
    "w": "ㅈ",
    "e": "ㄷ",
    "r": "ㄱ",
    "t": "ㅅ",
    "y": "ㅛ",
    "u": "ㅕ",
    "i": "ㅑ",
    "o": "ㅐ",
    "p": "ㅔ",
    "a": "ㅁ",
    "s": "ㄴ",
    "d": "ㅇ",
    "f": "ㄹ",
    "g": "ㅎ",
    "h": "ㅗ",
    "j": "ㅓ",
    "k": "ㅏ",
    "l": "ㅣ",
    "z": "ㅋ",
    "x": "ㅌ",
    "c": "ㅊ",
    "v": "ㅍ",
    "b": "ㅠ",
    "n": "ㅜ",
    "m": "ㅡ",
}

# 쌍자음/이중모음은 Shift가 눌린 상태지만, 조합키 판단에서는 동일하게 취급한다.
_SHIFTED_JAMO = {
    "ㅂ": "ㅃ",
    "ㅈ": "ㅉ",
    "ㄷ": "ㄸ",
    "ㄱ": "ㄲ",
    "ㅅ": "ㅆ",
    "ㅐ": "ㅒ",
    "ㅔ": "ㅖ",
}

# 역방향 매핑: 자모 → 알파벳 (소문자 기준)
_HANGUL_TO_LATIN = {value: key for key, value in _LATIN_TO_HANGUL.items()}
for base, shifted in _SHIFTED_JAMO.items():
    latin = _HANGUL_TO_LATIN.get(base)
    if latin:
        _HANGUL_TO_LATIN[shifted] = latin


def normalize_shortcut_key(key: str) -> str:
    """한글 IME에서 들어오는 키 문자열을 영문 기준으로 정규화한다.

    Textual은 `ctrl+ㅜ`처럼 자모 단위 키 문자열을 생성한다. 이 함수를
    통해 `ctrl+n`으로 변환하여 기존 단축키 정의와 일치시킨다.
    """

    if not key:
        return key

    parts: List[str] = key.split("+")
    normalized: List[str] = []

    for part in parts:
        lower = part.lower()
        if lower in _HANGUL_TO_LATIN:
            latin = _HANGUL_TO_LATIN[lower]
            normalized.append(latin.upper() if part.isupper() else latin)
        else:
            normalized.append(part)

    return "+".join(normalized)


def iter_hangul_variants(key: str) -> Iterable[str]:
    """주어진 단축키에 대해 한글 자모 변형을 생성한다."""

    if not key:
        return []

    parts = key.split("+")
    if not parts:
        return []

    base = parts[-1].lower()
    if base not in _LATIN_TO_HANGUL:
        return []

    hangul = _LATIN_TO_HANGUL[base]
    variants = ["+".join([*parts[:-1], hangul])]

    # Shift 조합 시 쌍자음/이중모음도 허용
    shifted = _SHIFTED_JAMO.get(hangul)
    if shifted:
        variants.append("+".join([*parts[:-1], shifted]))

    return variants


@dataclass(frozen=True)
class ShortcutDefinition:
    """확장 가능한 단축키 정의"""

    key: str
    action: str
    description: str
    show: bool = True
    priority: int = 0
    key_display: str | None = None


def expand_shortcut(definition: ShortcutDefinition) -> list[Binding]:
    """한글 변형을 포함한 Binding 리스트를 생성한다."""

    bindings = [
        Binding(
            definition.key,
            definition.action,
            definition.description,
            show=definition.show,
            priority=definition.priority,
            key_display=definition.key_display,
        )
    ]

    for variant in iter_hangul_variants(definition.key):
        if variant == definition.key:
            continue
        bindings.append(
            Binding(
                variant,
                definition.action,
                definition.description,
                show=False,
                priority=definition.priority,
                key_display=definition.key_display,
            )
        )

    return bindings


