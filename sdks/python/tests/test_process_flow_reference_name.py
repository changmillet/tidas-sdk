"""Both SDKs run the same reference-name conformance cases."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from tidas_sdk import analyze_process_flow_references, compose_flow_name
from tidas_sdk.core import collect_process_flow_references

FIXTURE = json.loads(
    (Path(__file__).parents[3] / "sdks/typescript/tests/fixtures/process-flow-reference-name.v1.json").read_text()
)


@pytest.mark.parametrize("example", FIXTURE["composition"], ids=lambda case: case["name"])
def test_compose_flow_name(example):
    before = deepcopy(example["fields"])
    result = compose_flow_name(example["fields"])
    assert result["description"] == example["description"]
    assert [issue["code"] for issue in result["issues"]] == example["codes"]
    assert example["fields"] == before


@pytest.mark.parametrize("example", FIXTURE["checks"], ids=lambda case: case["name"])
def test_process_flow_references(example):
    process = example["process"]
    flows = [FIXTURE["flows"][key] for key in example["evidence"]]
    before = deepcopy((process, flows))
    result = analyze_process_flow_references(process, flows=flows)
    assert result["profile"] == FIXTURE["profile"]
    assert result["complete"] == ("unresolved" not in example["statuses"])
    assert result["valid"] == (not example["codes"])
    assert [check["status"] for check in result["coverage"]] == example["statuses"]
    assert [issue["code"] for issue in result["validationIssues"]] == example["codes"]
    if "paths" in example:
        assert [issue["path"] for issue in result["validationIssues"]] == example["paths"]
    assert [ref["path"] for ref in collect_process_flow_references(process)] == [
        check["path"] for check in result["coverage"] if check["status"] != "not-applicable"
    ]
    assert (process, flows) == before
