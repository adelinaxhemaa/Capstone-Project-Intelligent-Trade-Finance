"""Unit tests for the tools layer: calculator, fuzzy matching, policy loader."""

from app.tools.calculator_tool import parse_amount, pct_difference, within_tolerance
from app.tools.fuzzy_match_tool import is_match, set_similarity, similarity
from app.tools.policy_loader import applied_layers, load_policy


def test_parse_amount():
    assert parse_amount("USD 1,234.50") == 1234.50
    assert parse_amount("84,750.00") == 84750.0
    assert parse_amount(1000) == 1000.0
    assert parse_amount("n/a") is None
    assert parse_amount(None) is None


def test_within_tolerance():
    ok, diff = within_tolerance("100300", "100000", 5.0)
    assert ok is True and round(diff, 2) == 0.30
    ok2, diff2 = within_tolerance("130000", "100000", 5.0)
    assert ok2 is False and round(diff2, 2) == 30.0
    ok3, diff3 = within_tolerance("oops", "100000", 5.0)
    assert ok3 is False and diff3 is None


def test_pct_difference_zero_reference():
    assert pct_difference(100, 0) is None


def test_fuzzy_matching():
    assert is_match("ACME Trading Co", "Acme Trading Company", 80)
    # token_set is subset-aware: suffix "Ltd" shouldn't break the match
    assert set_similarity("Darkstar Shipping Ltd", "Darkstar Shipping") == 100.0
    assert not is_match("Acme Trading Co", "Globex Industrial", 85)


def test_policy_layering():
    base = load_policy()
    assert base["amount_tolerance_pct"] == 5.0
    eu = load_policy("eu")
    assert eu["privacy"]["redact_pii_in_reports"] is True      
    assert eu["sanctions"]["lists"][0] == "EU"                 
    merged = load_policy("us", {"sanctions": {"match_threshold": 95}})
    assert merged["sanctions"]["match_threshold"] == 95         
    assert merged["sanctions"]["lists"][0] == "OFAC"            
    layers = applied_layers("us", {"x": 1})
    assert layers == ["base:policy_pack.yaml", "regional:us_policy.yaml", "bundle:sanctions_policy"]
