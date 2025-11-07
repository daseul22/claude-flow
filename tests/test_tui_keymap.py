"""Keymap 유틸리티 단위 테스트."""

import pytest

pytest.importorskip("textual", reason="textual 패키지가 필요합니다.")

from textual.binding import Binding  # noqa: E402

from src.presentation.tui.utils.keymap import (
    ShortcutDefinition,
    expand_shortcut,
    iter_hangul_variants,
    normalize_shortcut_key,
)


def test_normalize_shortcut_key_with_hangul_character() -> None:
    """한글 자모 단축키가 영문으로 변환되는지 확인한다."""

    assert normalize_shortcut_key("ctrl+ㅜ") == "ctrl+n"


def test_normalize_shortcut_key_keeps_ascii() -> None:
    """이미 ASCII인 단축키는 변경되지 않아야 한다."""

    assert normalize_shortcut_key("ctrl+/") == "ctrl+/"


def test_iter_hangul_variants_returns_expected_forms() -> None:
    """영문 단축키에서 한글 변형이 생성되는지 검사한다."""

    variants = set(iter_hangul_variants("ctrl+o"))
    assert variants == {"ctrl+ㅐ", "ctrl+ㅒ"}


def test_expand_shortcut_includes_hangul_binding() -> None:
    """Binding 확장 시 한글 변형이 포함되는지 확인한다."""

    definition = ShortcutDefinition("ctrl+n", "new_session", "새 세션")
    bindings = expand_shortcut(definition)
    keys = {binding.key for binding in bindings}

    assert "ctrl+n" in keys
    assert "ctrl+ㅜ" in keys
    # 한글 변형은 도움말에 노출되면 안 된다.
    hangul_binding = next(binding for binding in bindings if binding.key == "ctrl+ㅜ")
    assert hangul_binding.show is False


