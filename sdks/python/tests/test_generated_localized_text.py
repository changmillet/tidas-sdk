from pathlib import Path
import sys
from typing import get_args

import pytest
from pydantic import TypeAdapter, ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tidas_sdk.generated.tidas_data_types import (
    AnnualSupplyOrProductionVolumeMultiLang,
    AnnualSupplyOrProductionVolumeTextItem,
    FTMultiLang,
    Languages,
    LocalizedText1000Item,
    LocalizedText500Item,
    LocalizedTextItem,
    STMultiLang,
    StringMultiLang,
)
from tidas_sdk.core.multilang import MultiLangList, validate_multilang_entries


def test_localized_text_item_requires_schema_fields() -> None:
    item = LocalizedTextItem.model_validate(
        {"@xml:lang": "en", "#text": "English title"}
    )

    assert item.xml_lang == "en"
    assert item.text == "English title"

    with pytest.raises(ValidationError):
        LocalizedTextItem.model_validate({"#text": "English title"})

    with pytest.raises(ValidationError):
        LocalizedTextItem.model_validate({"@xml:lang": "en"})


def test_localized_text_item_enforces_tidas_language_enum() -> None:
    language_values = set(get_args(Languages))

    assert {"en", "de", "zh"}.issubset(language_values)
    assert "en-US" not in language_values

    LocalizedTextItem.model_validate({"@xml:lang": "de", "#text": "Deutscher Titel"})

    with pytest.raises(ValidationError):
        LocalizedTextItem.model_validate({"@xml:lang": "en-US", "#text": "English"})


def test_localized_text_specializations_preserve_max_length() -> None:
    LocalizedText500Item.model_validate({"@xml:lang": "fr", "#text": "a" * 500})
    LocalizedText1000Item.model_validate({"@xml:lang": "fr", "#text": "a" * 1000})

    with pytest.raises(ValidationError):
        LocalizedText500Item.model_validate({"@xml:lang": "fr", "#text": "a" * 501})

    with pytest.raises(ValidationError):
        LocalizedText1000Item.model_validate({"@xml:lang": "fr", "#text": "a" * 1001})


def test_multilang_aliases_reference_localized_text_models() -> None:
    string_array_type, string_item_type = get_args(StringMultiLang)
    st_array_type, st_item_type = get_args(STMultiLang)
    ft_array_type, ft_item_type = get_args(FTMultiLang)

    assert get_args(string_array_type)[0] == list[LocalizedText500Item]
    assert string_item_type is LocalizedText500Item

    assert get_args(st_array_type)[0] == list[LocalizedText1000Item]
    assert st_item_type is LocalizedText1000Item

    assert get_args(ft_array_type)[0] == list[LocalizedTextItem]
    assert ft_item_type is LocalizedTextItem


def test_annual_supply_volume_alias_preserves_patterned_item_type() -> None:
    annual_array_type, annual_item_type = get_args(
        AnnualSupplyOrProductionVolumeMultiLang
    )

    assert get_args(annual_array_type)[0] == list[AnnualSupplyOrProductionVolumeTextItem]
    assert annual_item_type is AnnualSupplyOrProductionVolumeTextItem

    AnnualSupplyOrProductionVolumeTextItem.model_validate(
        {"@xml:lang": "en", "#text": "12.5 kg reference flow"}
    )

    with pytest.raises(ValidationError):
        AnnualSupplyOrProductionVolumeTextItem.model_validate(
            {"@xml:lang": "en", "#text": "12.5"}
        )


def test_localized_text_item_rejects_en_text_with_chinese_characters() -> None:
    with pytest.raises(ValidationError):
        LocalizedTextItem.model_validate(
            {"@xml:lang": "en", "#text": "天工LCA数据团队"}
        )


def test_localized_text_item_rejects_zh_text_without_chinese_characters() -> None:
    with pytest.raises(ValidationError):
        LocalizedTextItem.model_validate(
            {"@xml:lang": "zh", "#text": "Tiangong LCA Data Team"}
        )


def test_multilang_list_rejects_non_tidas_language_code() -> None:
    values = MultiLangList()

    with pytest.raises(ValueError):
        values.set_text("English title", "en-US")


@pytest.mark.parametrize(
    "alias", [StringMultiLang, STMultiLang, FTMultiLang, AnnualSupplyOrProductionVolumeMultiLang]
)
def test_multilang_alias_requires_unique_language(alias: object) -> None:
    adapter = TypeAdapter(alias)
    first = {"@xml:lang": "en", "#text": "1 kg annual supply"}
    valid = [first, {"@xml:lang": "de", "#text": "1 kg Jahresmenge"}]
    assert len(adapter.validate_python(valid)) == 2
    adapter.validate_python(first)

    for duplicate in (first, {"@xml:lang": "en", "#text": "2 kg annual supply"}):
        with pytest.raises(ValidationError) as error:
            adapter.validate_python([first, duplicate])
        duplicate_issue = next(
            issue for issue in error.value.errors() if issue["type"] == "duplicate_language_entry"
        )
        assert duplicate_issue["ctx"] == {"language": "en", "index": 1, "first_index": 0}


def test_multilang_list_validation_reports_duplicates_without_rewriting() -> None:
    values = MultiLangList([
        {"@xml:lang": "en", "#text": "English title"},
        {"@xml:lang": "en", "#text": "Second paragraph"},
    ])
    original = values.to_plain_list()
    with pytest.raises(ValueError, match="Language en at index 1 already occurs at index 0"):
        validate_multilang_entries(values)
    assert values == original
