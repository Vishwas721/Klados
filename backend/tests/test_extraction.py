import pytest

from app.services.discovery.gmaps_extractor import (
    _extract_phone,
    _extract_place_id,
    _is_valid_website,
    _normalize_phone,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("+91 98450 12345", "9845012345"),
        ("919845012345", "9845012345"),
        ("09845012345", "9845012345"),
        ("044 2345 6789", "04423456789"),  # landline keeps its STD 0
        ("8041234567", "8041234567"),
        ("12345", None),
        ("18001024663", None),  # toll-free: no WhatsApp, so not a usable lead
    ],
)
def test_normalize_phone(raw, expected):
    assert _normalize_phone(raw) == expected


def test_extract_phone_from_card_text():
    text = "Smile Dental\n4.6 (120)\nDentist · 12th Main\nOpen ⋅ Closes 8 pm · 098450 12345"
    assert _extract_phone(text) == "9845012345"


def test_extract_place_id():
    assert _extract_place_id("https://www.google.com/maps/place/x/data=!4m7!1sChIJabc-_123") == "ChIJabc-_123"
    assert _extract_place_id("https://maps/x/data=!1s0x3bae1:0x9f2a!8m2") == "0x3bae1:0x9f2a"
    assert _extract_place_id(None) is None


@pytest.mark.parametrize(
    "url, ok",
    [
        ("https://smiledental.in", True),
        ("http://www.example.co.in/home", True),
        ("https://www.justdial.com/Bangalore/x", False),
        ("https://business.google.com/site", False),
        ("ftp://example.com", False),
        (None, False),
    ],
)
def test_is_valid_website(url, ok):
    assert _is_valid_website(url) is ok
