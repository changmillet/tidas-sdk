"""
Utilities for handling TIDAS multi-language text arrays.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any, Iterable, MutableSequence, Protocol, TypedDict, TypeVar

from pydantic_core import PydanticCustomError

MultiLangItem = TypedDict(
    "MultiLangItem",
    {"@xml:lang": str, "#text": str},
    total=False,
)

CHINESE_CHARACTER_PATTERN = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]")
TIDAS_LANGUAGE_CODES = frozenset(
    (
        "aa",
        "ab",
        "ae",
        "af",
        "ak",
        "am",
        "an",
        "ar",
        "as",
        "av",
        "ay",
        "az",
        "ba",
        "be",
        "bg",
        "bh",
        "bi",
        "bm",
        "bn",
        "bo",
        "br",
        "bs",
        "ca",
        "ce",
        "ch",
        "co",
        "cr",
        "cs",
        "cu",
        "cv",
        "cy",
        "da",
        "de",
        "dv",
        "dz",
        "ee",
        "el",
        "en",
        "eo",
        "es",
        "et",
        "eu",
        "fa",
        "ff",
        "fi",
        "fj",
        "fo",
        "fr",
        "fy",
        "ga",
        "gd",
        "gl",
        "gn",
        "gu",
        "gv",
        "ha",
        "he",
        "hi",
        "ho",
        "hr",
        "ht",
        "hu",
        "hy",
        "hz",
        "ia",
        "id",
        "ie",
        "ig",
        "ii",
        "ik",
        "io",
        "is",
        "it",
        "iu",
        "ja",
        "jv",
        "ka",
        "kg",
        "ki",
        "kj",
        "kk",
        "kl",
        "km",
        "kn",
        "ko",
        "kr",
        "ks",
        "ku",
        "kv",
        "kw",
        "ky",
        "la",
        "lb",
        "lg",
        "li",
        "ln",
        "lo",
        "lt",
        "lu",
        "lv",
        "mg",
        "mh",
        "mi",
        "mk",
        "ml",
        "mn",
        "mo",
        "mr",
        "ms",
        "mt",
        "my",
        "na",
        "nb",
        "nd",
        "ne",
        "ng",
        "nl",
        "nn",
        "no",
        "nr",
        "nv",
        "ny",
        "oc",
        "oj",
        "om",
        "or",
        "os",
        "pa",
        "pi",
        "pl",
        "ps",
        "pt",
        "qu",
        "rm",
        "rn",
        "ro",
        "ru",
        "rw",
        "sa",
        "sc",
        "sd",
        "se",
        "sg",
        "si",
        "sk",
        "sl",
        "sm",
        "sn",
        "so",
        "sq",
        "sr",
        "ss",
        "st",
        "su",
        "sv",
        "sw",
        "ta",
        "te",
        "tg",
        "th",
        "ti",
        "tk",
        "tl",
        "tn",
        "to",
        "tr",
        "ts",
        "tt",
        "tw",
        "ty",
        "ug",
        "uk",
        "ur",
        "uz",
        "ve",
        "vi",
        "vo",
        "wa",
        "wo",
        "xh",
        "yi",
        "yo",
        "za",
        "zh",
        "zu",
    )
)


class MultiLangList(list[MultiLangItem]):
    """
    List wrapper that exposes convenient helpers for language specific entries.
    """

    def __init__(self, values: Iterable[MultiLangItem] | None = None) -> None:
        super().__init__()
        if not values:
            return
        for value in values:
            lang = value.get("@xml:lang")
            text = value.get("#text")
            if lang and text is not None:
                self.append({"@xml:lang": lang, "#text": text})

    def set_text(self, text: str, lang: str = "en") -> None:
        """
        Upsert the text for a specific locale.
        """
        validate_multilang_item({"@xml:lang": lang, "#text": text})
        for entry in self:
            if entry.get("@xml:lang") == lang:
                entry["#text"] = text
                return
        self.append({"@xml:lang": lang, "#text": text})

    def get_text(self, lang: str | None = "en") -> str | None:
        """
        Fetch the best matching text for the requested language.
        """
        if lang:
            for entry in self:
                if entry.get("@xml:lang") == lang:
                    return entry.get("#text")
        return self[0].get("#text") if self else None

    def to_plain_list(self) -> list[MultiLangItem]:
        """
        Produce a JSON serializable representation.
        """
        return [
            {"@xml:lang": item.get("@xml:lang", ""), "#text": item.get("#text", "")}
            for item in self
        ]


def _is_multilang_item(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and "@xml:lang" in value
        and "#text" in value
        and isinstance(value.get("@xml:lang"), str)
        and (value.get("#text") is None or isinstance(value.get("#text"), str))
    )


def _is_multilang_list(value: Any) -> bool:
    if not isinstance(value, MutableSequence):
        return False
    if not value:
        return False
    return all(_is_multilang_item(entry) for entry in value)


def validate_multilang_item(value: MultiLangItem) -> None:
    lang = value.get("@xml:lang")
    text = value.get("#text")

    if not isinstance(lang, str) or not isinstance(text, str):
        return

    if lang not in TIDAS_LANGUAGE_CODES:
        raise ValueError(
            f"@xml:lang '{lang}' is not a TIDAS Languages enumeration value"
        )

    if lang == "zh" and not CHINESE_CHARACTER_PATTERN.search(text):
        raise ValueError(
            "@xml:lang value 'zh' must include at least one Chinese character"
        )

    if lang == "en" and CHINESE_CHARACTER_PATTERN.search(text):
        raise ValueError("@xml:lang value 'en' must not contain Chinese characters")


def validate_multilang_entries(values: Iterable[MultiLangItem]) -> None:
    def languages() -> Iterable[str | None]:
        for value in values:
            validate_multilang_item(value)
            yield value.get("@xml:lang")

    _validate_unique_languages(languages())


class _LocalizedTextModel(Protocol):
    @property
    def xml_lang(self) -> str: ...


_LocalizedTextModelT = TypeVar("_LocalizedTextModelT", bound=_LocalizedTextModel)


def validate_multilang_models(values: list[_LocalizedTextModelT]) -> list[_LocalizedTextModelT]:
    _validate_unique_languages(value.xml_lang for value in values)
    return values


def duplicate_localized_languages(
    languages: Iterable[str | None],
) -> Iterator[tuple[str, int, int]]:
    first_by_language: dict[str, int] = {}
    for index, language in enumerate(languages):
        if not isinstance(language, str) or language not in TIDAS_LANGUAGE_CODES:
            continue
        if language in first_by_language:
            yield language, index, first_by_language[language]
        else:
            first_by_language[language] = index


def _validate_unique_languages(languages: Iterable[str | None]) -> None:
    for language, index, first_index in duplicate_localized_languages(languages):
        raise PydanticCustomError(
            "duplicate_language_entry",
            "Language {language} at index {index} already occurs at index {first_index}",
            {"language": language, "index": index, "first_index": first_index},
        )


def wrap_multilang(value: Any) -> Any:
    """
    Convert dictionaries/lists from JSON payloads into their pythonic wrappers.
    """
    if _is_multilang_list(value):
        return MultiLangList(value)
    if _is_multilang_item(value):
        return MultiLangList([value])
    return value


def deep_wrap_multilang(payload: Any) -> Any:
    """
    Recursively walk payloads (dict/list) and wrap multi-language nodes.
    """
    if isinstance(payload, dict):
        return wrap_multilang({k: deep_wrap_multilang(v) for k, v in payload.items()})
    if isinstance(payload, list):
        wrapped_items = [deep_wrap_multilang(item) for item in payload]
        flattened_items: list[MultiLangItem] = []
        for item in wrapped_items:
            if isinstance(item, MultiLangList):
                flattened_items.extend(item.to_plain_list())
                continue
            if _is_multilang_item(item):
                flattened_items.append(item)
                continue
            return wrapped_items
        return MultiLangList(flattened_items) if flattened_items else wrapped_items
    return payload
