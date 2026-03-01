from urllib.parse import urlparse

_SIMPLE_ICONS_CDN = "https://cdn.simpleicons.org"
_GOOGLE_FAVICON = "https://www.google.com/s2/favicons?domain={domain}&sz=32"

_APP_ICON_MAP: dict[str, tuple[str, str]] = {
    "firefox": ("firefox", "FF7139"),
    "firefox-esr": ("firefox", "FF7139"),
    "navigator": ("firefox", "FF7139"),
    "google-chrome": ("googlechrome", "4285F4"),
    "chromium": ("chromium", "4587F5"),
    "chromium-browser": ("chromium", "4587F5"),
    "brave-browser": ("brave", "FB542B"),
    "code": ("visualstudiocode", "007ACC"),
    "code - oss": ("visualstudiocode", "007ACC"),
    "cursor": ("cursor", "000000"),
    "slack": ("slack", "4A154B"),
    "discord": ("discord", "5865F2"),
    "telegram-desktop": ("telegram", "26A5E4"),
    "telegramdesktop": ("telegram", "26A5E4"),
    "spotify": ("spotify", "1DB954"),
    "obsidian": ("obsidian", "7C3AED"),
    "notion": ("notion", "000000"),
    "notion-app": ("notion", "000000"),
    "postman": ("postman", "FF6C37"),
    "figma-linux": ("figma", "F24E1E"),
    "gimp-2.10": ("gimp", "5C5543"),
    "gimp": ("gimp", "5C5543"),
    "inkscape": ("inkscape", "000000"),
    "libreoffice": ("libreoffice", "18A303"),
    "thunderbird": ("thunderbird", "0A84FF"),
    "signal": ("signal", "3A76F0"),
    "zoom": ("zoom", "0B5CFF"),
    "vlc": ("vlcmediaplayer", "FF8800"),
    "steam": ("steam", "000000"),
    "alacritty": ("alacritty", "F46D01"),
    "kitty": ("kitty", "000000"),
    "wezterm": ("wezterm", "4E49EE"),
    "docker-desktop": ("docker", "2496ED"),
    "blender": ("blender", "E87D0D"),
    "obs": ("obsstudio", "302E31"),
    "insomnia": ("insomnia", "4000BF"),
    "dbeaver": ("dbeaver", "382923"),
    "datagrip": ("datagrip", "000000"),
    "webstorm": ("webstorm", "000000"),
    "pycharm": ("pycharm", "000000"),
    "intellij idea": ("intellijidea", "000000"),
    "clion": ("clion", "000000"),
    "goland": ("goland", "000000"),
    "rider": ("rider", "000000"),
}


def resolve_session_icon(
    app_name: str, url: str | None = None,
) -> tuple[str | None, str | None]:
    if url:
        try:
            parsed = urlparse(url)
            domain = parsed.hostname
            if domain:
                return _GOOGLE_FAVICON.format(domain=domain), None
        except Exception:
            pass

    entry = _APP_ICON_MAP.get(app_name.lower())
    if entry:
        slug, color = entry
        return f"{_SIMPLE_ICONS_CDN}/{slug}/{color}", f"#{color}"

    return None, None
