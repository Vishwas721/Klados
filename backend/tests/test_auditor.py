import pytest

from app.services.auditor.site_auditor import classify_site, describe_unreachable
from app.services.auditor.tech_detector import detect_stack


@pytest.mark.parametrize(
    "ssl, mobile, ttfb, dom, expected",
    [
        (False, True, 100, 500, "DIGITAL_DINOSAUR"),
        (True, False, 100, 500, "DIGITAL_DINOSAUR"),
        (True, True, 2000, 500, "LAGGY_UX"),
        (True, True, 100, 5000, "LAGGY_UX"),
        (True, True, 100, 500, "AUTOMATION_CANDIDATE"),
    ],
)
def test_classify_site(ssl, mobile, ttfb, dom, expected):
    assert classify_site(ssl, mobile, ttfb, dom) == expected


def test_describe_unreachable():
    assert describe_unreachable("Page.goto: NS_ERROR_UNKNOWN_HOST\nCall log: ...") == (
        "Website unreachable (NS_ERROR_UNKNOWN_HOST)"
    )
    assert describe_unreachable("Page.goto: something else") is None


def test_detect_stack_wordpress_with_whatsapp_and_practo():
    html = """
    <link rel="stylesheet" href="/wp-content/themes/x/style.css">
    <script src="https://www.googletagmanager.com/gtag/js?id=G-1"></script>
    <a href="https://wa.me/919845012345">Chat</a>
    <iframe src="https://widget.practo.com/book"></iframe>
    """
    result = detect_stack(html)
    assert result["detected_tech"] == ["WordPress", "Google Analytics", "WhatsApp", "Practo"]
    assert result["has_chat_widget"] is True
    assert result["has_online_booking"] is True


def test_detect_stack_plain_site():
    result = detect_stack("<html><body><h1>Sri Lakshmi Stores</h1></body></html>")
    assert result == {"detected_tech": [], "has_chat_widget": False, "has_online_booking": False}


def test_detect_stack_handles_missing_html():
    assert detect_stack(None)["detected_tech"] == []
