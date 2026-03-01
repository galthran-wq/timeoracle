from src.services.icon_resolver import resolve_session_icon


def test_known_app_returns_icon_and_color():
    icon, color = resolve_session_icon("firefox")
    assert icon is not None
    assert "simpleicons.org" in icon
    assert "firefox" in icon
    assert color == "#FF7139"


def test_known_app_case_insensitive():
    assert resolve_session_icon("Firefox") == resolve_session_icon("firefox")
    assert resolve_session_icon("SLACK") == resolve_session_icon("slack")
    assert resolve_session_icon("Code") == resolve_session_icon("code")


def test_unknown_app_returns_none_tuple():
    assert resolve_session_icon("my-custom-app") == (None, None)
    assert resolve_session_icon("xterm") == (None, None)


def test_url_returns_favicon_no_brand_color():
    icon, color = resolve_session_icon("firefox", "https://github.com/anthropics/claude")
    assert icon is not None
    assert "google.com/s2/favicons" in icon
    assert "domain=github.com" in icon
    assert color is None


def test_url_takes_priority_over_app_name():
    icon, color = resolve_session_icon("firefox", "https://example.com/page")
    assert "google.com/s2/favicons" in icon
    assert "domain=example.com" in icon
    assert color is None


def test_malformed_url_falls_back_to_app_name():
    icon, color = resolve_session_icon("firefox", "not-a-url")
    assert icon is not None
    assert "simpleicons.org" in icon
    assert color == "#FF7139"


def test_empty_url_falls_back_to_app_name():
    icon, color = resolve_session_icon("slack", "")
    assert icon is not None
    assert "simpleicons.org" in icon
    assert color == "#4A154B"


def test_url_without_hostname_falls_back():
    icon, color = resolve_session_icon("discord", "file:///tmp/test.html")
    assert icon is not None
    assert "simpleicons.org" in icon
    assert color == "#5865F2"


def test_none_url_uses_app_name():
    icon, color = resolve_session_icon("spotify", None)
    assert icon is not None
    assert "spotify" in icon
    assert color == "#1DB954"


def test_unknown_app_with_bad_url_returns_none():
    assert resolve_session_icon("xterm", "not-a-url") == (None, None)


def test_brand_colors_are_valid_hex():
    for app in ["firefox", "code", "slack", "discord", "spotify"]:
        _, color = resolve_session_icon(app)
        assert color is not None
        assert color.startswith("#")
        assert len(color) == 7
