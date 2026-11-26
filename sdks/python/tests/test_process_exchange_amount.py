import copy
import json
from pathlib import Path

import pytest

from pydantic import ValidationError

from tidas_sdk import create_process
from tidas_sdk.generated.tidas_processes import ExchangesExchangeItem

DATA = Path(__file__).resolve().parents[3] / "test-data"
CASES = json.loads((DATA / "process-exchange-amount-cases.json").read_text())
CONTROL = json.loads((DATA / "process-exchange-amount-control.json").read_text())


@pytest.mark.parametrize("case", CASES)
def test_process_exchange_amount(case):
    data = copy.deepcopy(CONTROL)
    rows = data["processDataSet"]["exchanges"]["exchange"]
    values = {k: v for k, v in case.items() if k != "conflict"}
    rows.append({**rows[0], "@dataSetInternalID": "2", **values})
    before = copy.deepcopy(data)
    process = create_process(data)
    assert process.validate() is not case["conflict"]
    if case["conflict"]:
        errors = process.last_validation_error().errors()
        fault = next(e for e in errors if e["type"] == "process_exchange_amount_conflict")
        assert fault["loc"] == ("processDataSet", "exchanges", "exchange", 1, "resultingAmount")
        assert fault["ctx"] == {k: values[k] for k in ("meanAmount", "resultingAmount")}
    assert process.validate(mode="jsonschema") is not case["conflict"]
    assert data == before


def test_direct_exchange_reports_field_location_and_original_amounts():
    process = create_process(copy.deepcopy(CONTROL))
    assert process.validate()
    row = process.process_data_set.exchanges.exchange[0]
    values = dict(row)
    values.update(mean_amount="1.01", resulting_amount="101")
    with pytest.raises(ValidationError) as error:
        ExchangesExchangeItem.model_validate(values)
    issue = next(e for e in error.value.errors() if e["type"] == "process_exchange_amount_conflict")
    assert issue["loc"] == ("resulting_amount",)
    assert issue["ctx"] == {"meanAmount": "1.01", "resultingAmount": "101"}
