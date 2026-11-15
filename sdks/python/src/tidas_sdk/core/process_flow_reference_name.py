"""Pure validation and construction of exact Process exchange Flow names."""

import re
from typing import Any, TypedDict
from unicodedata import normalize

from .multilang import TIDAS_LANGUAGE_CODES, duplicate_localized_languages

PROCESS_FLOW_REFERENCE_NAME_PROFILE = "tidas.process-flow-reference-name.v1"

_NAME_FIELDS = ("baseName", "treatmentStandardsRoutes", "mixAndLocationTypes", "flowProperties")
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_VERSION = re.compile(r"[0-9]{2}\.[0-9]{2}(\.[0-9]{3})?")
_MAX_LENGTH = 1000

Path = list[str | int]


class ExactFlowNameEvidence(TypedDict):
    uuid: str
    version: str
    document: Any


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _entries(value: Any, path: Path) -> list[tuple[Any, Path]]:
    if isinstance(value, list):
        return [(item, [*path, index]) for index, item in enumerate(value)]
    return [(value, path)] if value is not _ABSENT else []


_ABSENT = object()


def _issue(code: str, path: Path, message: str, **params: str | int) -> dict[str, Any]:
    return {
        "code": code,
        "path": path,
        "message": message,
        "params": params,
        "severity": "error",
        "rawCode": "process_flow_reference_name",
    }


def _text(value: str) -> str:
    return normalize("NFC", value.strip(" \t\r\n"))


def _localized(raw: Any, path: Path, issues: list[dict[str, Any]]) -> dict[str, str]:
    entries = _entries(raw, path)
    if isinstance(raw, list):
        for lang, index, first in duplicate_localized_languages(
            _object(item).get("@xml:lang") for item in raw
        ):
            issues.append(_issue(
                "duplicate_language_entry", [*path, index, "@xml:lang"],
                f"Language {lang} already occurs at index {first} in this field.",
                language=lang, firstIndex=first,
            ))
    result: dict[str, str] = {}
    for value, item_path in entries:
        item = _object(value)
        lang, text = item.get("@xml:lang"), item.get("#text")
        if not isinstance(lang, str) or lang not in TIDAS_LANGUAGE_CODES or not isinstance(text, str):
            issues.append(_issue(
                "flow_name_text_invalid", item_path, "A supported language and text are required.",
            ))
        elif lang not in result:
            result[lang] = _text(text)
    return result


def _usable(text: str | None) -> bool:
    return text not in (None, "", "-")


def compose_flow_name(name: Any) -> dict[str, Any]:
    """Compose each language from the four declared Flow name fields."""
    issues: list[dict[str, Any]] = []
    data = _object(name)
    base, *qualifiers = [
        _localized(data.get(field, _ABSENT), [field], issues) for field in _NAME_FIELDS
    ]
    languages = set(base)
    for segment in qualifiers:
        languages.update(lang for lang, text in segment.items() if _usable(text))
    if not languages:
        issues.append(_issue(
            "flow_name_base_missing", ["baseName"], "A substantive Flow base name is required.",
        ))
    description: list[dict[str, str]] = []
    for language in sorted(languages):
        base_text = base.get(language, "")
        if not _usable(base_text):
            issues.append(_issue(
                "flow_name_base_missing", ["baseName"],
                "Missing substantive Flow base name for this language.", language=language,
            ))
            continue
        parts = [base_text]
        for field, segment in zip(_NAME_FIELDS[1:], qualifiers, strict=True):
            text = segment.get(language, "")
            if _usable(text):
                parts.append(text)
            elif any(map(_usable, segment.values())):
                issues.append(_issue(
                    "flow_name_translation_missing", [field],
                    "A populated Flow name segment lacks this translation.",
                    language=language, field=field,
                ))
        text = "; ".join(parts)
        if len(text) > _MAX_LENGTH:
            issues.append(_issue(
                "flow_name_too_long", [], "The full Flow name exceeds the reference description limit.",
                language=language, length=len(text), maximum=_MAX_LENGTH,
            ))
        description.append({"@xml:lang": language, "#text": text})
    return {"description": [] if issues else description, "issues": issues}


def collect_process_flow_references(process: Any) -> list[dict[str, Any]]:
    """Return every exchange reference and its location, including invalid identities."""
    root = _object(_object(process).get("processDataSet"))
    collection_path: Path = ["processDataSet", "exchanges", "exchange"]
    references: list[dict[str, Any]] = []
    for exchange, path in _entries(_object(root.get("exchanges")).get("exchange", _ABSENT), collection_path):
        ref_path = [*path, "referenceToFlowDataSet"]
        entries = _entries(_object(exchange).get("referenceToFlowDataSet", _ABSENT), ref_path)
        for value, item_path in entries or [(None, ref_path)]:
            ref = _object(value)
            uuid, version = ref.get("@refObjectId"), ref.get("@version")
            references.append({
                "path": item_path,
                "uuid": uuid if isinstance(uuid, str) else "",
                "version": version if isinstance(version, str) else "",
                **({"description": ref["common:shortDescription"]} if "common:shortDescription" in ref else {}),
            })
    return references


def _bind_name(evidence: ExactFlowNameEvidence) -> tuple[dict[str, Any] | None, str | None]:
    root = _object(_object(evidence["document"]).get("flowDataSet"))
    info = _object(_object(root.get("flowInformation")).get("dataSetInformation"))
    publication = _object(_object(root.get("administrativeInformation")).get("publicationAndOwnership"))
    uuid, version = info.get("common:UUID"), publication.get("common:dataSetVersion")
    if uuid != evidence["uuid"] or not isinstance(version, str):
        return None, "flow_reference_evidence_invalid"
    if version != evidence["version"]:
        return None, "flow_reference_version_mismatch"
    return compose_flow_name(info.get("name")), None


def _check_reference(
    ref: dict[str, Any],
    by_identity: dict[tuple[str, str], tuple[Any, dict[str, Any] | None, str | None]],
    known_uuids: set[str],
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    path, uuid, version = ref["path"], ref["uuid"], ref["version"]
    identity = {"uuid": uuid, "version": version}
    scope = {"path": path, **identity}

    def report(status: str, code: str, message: str) -> dict[str, Any]:
        issues.append(_issue(code, path, message, **identity))
        return {**scope, "status": status}

    if not _UUID.fullmatch(uuid) or not _VERSION.fullmatch(version):
        return report("invalid", "flow_reference_inexact", "Flow reference requires an exact UUID and version.")
    evidence = by_identity.get((uuid, version))
    if evidence is None:
        code = "flow_reference_version_mismatch" if uuid in known_uuids else "flow_reference_evidence_unavailable"
        return report("unresolved", code, "Evidence for the selected Flow version was not supplied.")
    _, composed, error = evidence
    if error is not None:
        return report("unresolved", error, "Supplied Flow evidence is invalid or conflicting for this reference.")
    assert composed is not None
    if composed["issues"]:
        for finding in composed["issues"]:
            issues.append({
                **finding,
                "path": path,
                "params": {
                    **finding["params"], **identity,
                    "flowNamePath": ".".join(map(str, finding["path"])),
                },
            })
        return {**scope, "status": "unresolved"}

    description_path = [*path, "common:shortDescription"]
    findings: list[dict[str, Any]] = []
    actual = _localized(ref.get("description", _ABSENT), description_path, findings)
    expected_description = composed["description"]
    expected = {item["@xml:lang"]: item["#text"] for item in expected_description}
    if not findings:
        for language in sorted(expected.keys() | actual.keys()):
            if expected.get(language) != actual.get(language):
                findings.append(_issue(
                    "flow_reference_description_mismatch", description_path,
                    "The exchange description differs from the selected Flow name.",
                    language=language, expected=expected.get(language, ""),
                    actual=actual.get(language, ""),
                ))
    issues.extend({**finding, "params": {**finding["params"], **identity}} for finding in findings)
    return {**scope, "expectedDescription": expected_description, "status": "invalid" if findings else "passed"}


def analyze_process_flow_references(
    process: Any, *, flows: list[ExactFlowNameEvidence] | None = None,
) -> dict[str, Any]:
    """Check all exchange names with caller-provided exact Flow evidence."""
    by_identity: dict[tuple[str, str], tuple[Any, dict[str, Any] | None, str | None]] = {}
    known_uuids: set[str] = set()
    for evidence in flows or []:
        key = (evidence["uuid"], evidence["version"])
        document = evidence["document"]
        known_uuids.add(evidence["uuid"])
        earlier = by_identity.get(key)
        if earlier is None:
            by_identity[key] = (document, *_bind_name(evidence))
        elif earlier[0] != document:
            by_identity[key] = (earlier[0], None, "flow_reference_evidence_conflict")

    issues: list[dict[str, Any]] = []
    coverage = [
        _check_reference(ref, by_identity, known_uuids, issues)
        for ref in collect_process_flow_references(process)
    ]
    if not coverage:
        coverage.append({
            "path": ["processDataSet", "exchanges", "exchange"],
            "uuid": "", "version": "", "status": "not-applicable",
        })
    return {
        "profile": PROCESS_FLOW_REFERENCE_NAME_PROFILE,
        "complete": all(check["status"] != "unresolved" for check in coverage),
        "valid": not issues,
        "coverage": coverage,
        "validationIssues": issues,
    }
