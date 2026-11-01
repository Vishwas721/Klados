"""Indian phone number normalization backed by libphonenumber.

Digit patterns alone can't tell a Bengaluru landline (080 4123 4567) from a
mobile written with a trunk 0 (080501 23456): most of our target cities have
STD codes starting with 7 or 8. libphonenumber carries the real numbering
plan, so we let it decide.

Storage format:
- mobile (including ranges shared by mobiles and landlines): 10 digits
- landline: trunk 0 + STD code + subscriber, e.g. 08041234567
The leading 0 is what marks a stored number as a landline (no WhatsApp).
"""

import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberType

_MOBILE_TYPES = {PhoneNumberType.MOBILE, PhoneNumberType.FIXED_LINE_OR_MOBILE}


def normalize_indian_phone(raw: str | None) -> str | None:
    """Return the stored form of an Indian number, or None if unusable.

    Toll-free, premium, shared-cost and invalid numbers return None: they
    can't be pitched on WhatsApp or reliably reach the business.
    """
    if not raw or not raw.strip():
        return None
    try:
        parsed = phonenumbers.parse(raw, "IN")
    except NumberParseException:
        return None
    if parsed.country_code != 91 or not phonenumbers.is_valid_number(parsed):
        return None

    national = str(parsed.national_number)
    number_type = phonenumbers.number_type(parsed)
    if number_type in _MOBILE_TYPES:
        return national
    if number_type == PhoneNumberType.FIXED_LINE:
        return f"0{national}"
    return None


def is_landline(stored: str) -> bool:
    return stored.startswith("0")
