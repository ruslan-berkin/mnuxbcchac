from typing import get_args

from reqcheck.criteria import CRITERIA, REQUIREMENT_CODES, SET_CODES, CriterionCode, criteria_for_prompt
from reqcheck.models import Anchor, Finding


def test_all_codes_defined_with_references():
    assert set(CRITERIA) == set(get_args(CriterionCode))
    assert len(REQUIREMENT_CODES) == 9 and len(SET_CODES) == 8
    for c in CRITERIA.values():
        assert c.title and c.how_to_check
        assert "29148" in c.reference or "830" in c.reference
    assert all(CRITERIA[c].scope == "requirement" for c in REQUIREMENT_CODES)
    assert all(CRITERIA[c].scope == "set" for c in SET_CODES)


def test_prompt_list_is_closed_per_scope():
    req = criteria_for_prompt("requirement")
    assert "- VER" in req and "S-CON" not in req
    assert "S-CON" in criteria_for_prompt("set")


def test_finding_rejects_unknown_criterion():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Finding(id="D-001", scope="set", criterion="XXX", severity="minor", quotes=["q"],
                anchors=[Anchor(line_start=1, line_end=1)], problem="p", fix="f", source="llm")
