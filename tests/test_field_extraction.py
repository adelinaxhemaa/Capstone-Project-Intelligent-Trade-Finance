from app.parsing.field_extraction import extract_value


def test_swift_field_tag_inline():
    text = "Documentary Credit Number (Field 20) HMB-ILC-2026-0784"
    assert extract_value(text, [r"credit number"], "id") == "HMB-ILC-2026-0784"


def test_value_on_next_line():
    text = "Beneficiary (Field 59)\nNordic Components GmbH\nSpeicherstadt 18"
    assert extract_value(text, [r"beneficiary"], "name") == "Nordic Components GmbH"


def test_date_with_trailing_prose():
    text = "Expiry Date and Place (Field 31D) 30 June 2026 at counters of Hanseatic Bank"
    assert extract_value(text, [r"expiry date and place", r"expiry"], "date") == "2026-06-30"


def test_amount_and_currency():
    text = "Currency / Amount (Field 32B) USD 84,750.00"
    assert extract_value(text, [r"currency\s*/\s*amount", r"amount"], "amount") == "84,750.00"
    assert extract_value(text, [r"currency\s*/\s*amount", r"currency"], "currency") == "USD"


def test_parenthetical_label_stripped():
    # "(Beneficiary)" is not a SWIFT tag but must still be stripped for names
    text = "Seller (Beneficiary): Acme Trading Co"
    assert extract_value(text, [r"seller"], "name") == "Acme Trading Co"


def test_validation_rejects_garbage():
    # No real date present -> None (so the field flags low-confidence -> LLM backstop)
    text = "Expiry Date and Place: see attached schedule"
    assert extract_value(text, [r"expiry date"], "date") is None
    # No id token with a digit
    assert extract_value("Reference: pending", [r"reference"], "id") is None


def test_flag_extraction():
    assert extract_value("Partial Shipments (Field 43P) Not allowed", [r"partial shipment"], "flag") == "prohibited"
    assert extract_value("Transhipment (Field 43T) Allowed", [r"transhipment"], "flag") == "allowed"


def test_missing_label_returns_none():
    assert extract_value("nothing relevant here", [r"invoice number"], "id") is None