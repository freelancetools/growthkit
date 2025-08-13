"""
Tests for core, pure utilities in `growthkit.connectors.mail.gmail_sync`.

- clean_subject: decodes encoded subjects and strips encoding artifacts
- clean_email_content: removes invisible chars/whitespace noise and shortens long URLs

To avoid importing heavy optional dependencies (google APIs, markitdown),
we stub them in sys.modules before importing the target module.
"""

import sys
import types
import importlib


def _load_gmail_sync_module():
    """Import `growthkit.connectors.mail.gmail_sync` with stubbed heavy deps."""
    # Create minimal stubs for external libs used at import time
    # google.auth.transport.requests.Request
    google_pkg = types.ModuleType("google")
    google_auth = types.ModuleType("google.auth")
    google_auth_transport = types.ModuleType("google.auth.transport")
    google_auth_transport_requests = types.ModuleType("google.auth.transport.requests")

    class _Request:  # noqa: D401
        """Stub request type"""

    google_auth_transport_requests.Request = _Request

    google_auth_exceptions = types.ModuleType("google.auth.exceptions")

    class _RefreshError(Exception):
        pass

    google_auth_exceptions.RefreshError = _RefreshError

    # google_auth_oauthlib.flow.InstalledAppFlow
    google_auth_oauthlib = types.ModuleType("google_auth_oauthlib")
    google_auth_oauthlib_flow = types.ModuleType("google_auth_oauthlib.flow")

    class _Flow:
        def run_local_server(self, _port=0):
            return object()

        @classmethod
        def from_client_secrets_file(cls, *_args, **_kwargs):
            return cls()

    google_auth_oauthlib_flow.InstalledAppFlow = _Flow

    # googleapiclient.discovery.build
    googleapiclient = types.ModuleType("googleapiclient")
    googleapiclient_discovery = types.ModuleType("googleapiclient.discovery")

    def _build(*_args, **_kwargs):
        return object()

    googleapiclient_discovery.build = _build

    # googleapiclient.errors.HttpError
    googleapiclient_errors = types.ModuleType("googleapiclient.errors")

    class _HttpError(Exception):
        def __init__(self, *_args, **_kwargs):
            self.resp = types.SimpleNamespace(status=None)

    googleapiclient_errors.HttpError = _HttpError

    # markitdown.MarkItDown
    markitdown = types.ModuleType("markitdown")

    class _MarkItDown:
        def convert_stream(self, _stream, _file_extension=".html"):
            return types.SimpleNamespace(text_content="")

    markitdown.MarkItDown = _MarkItDown

    # Register stubs
    sys.modules.setdefault("google", google_pkg)
    sys.modules.setdefault("google.auth", google_auth)
    sys.modules.setdefault("google.auth.transport", google_auth_transport)
    sys.modules.setdefault("google.auth.transport.requests", google_auth_transport_requests)
    sys.modules.setdefault("google.auth.exceptions", google_auth_exceptions)
    sys.modules.setdefault("google_auth_oauthlib", google_auth_oauthlib)
    sys.modules.setdefault("google_auth_oauthlib.flow", google_auth_oauthlib_flow)
    sys.modules.setdefault("googleapiclient", googleapiclient)
    sys.modules.setdefault("googleapiclient.discovery", googleapiclient_discovery)
    sys.modules.setdefault("googleapiclient.errors", googleapiclient_errors)
    sys.modules.setdefault("markitdown", markitdown)

    # Import target module after stubbing
    return importlib.import_module("growthkit.connectors.mail.gmail_sync")


def test_clean_subject_decoding_and_artifacts():
    """Subjects are decoded and encoding artifacts removed, with trimming."""
    gmail_sync_mod = _load_gmail_sync_module()
    # Encoded subject (quoted-printable style within RFC 2047)
    encoded = "=?UTF-8?Q?Hello_=F0=9F=91=8B_World?="
    # Also include stray artifact tokens that should be stripped
    noisy = f"{encoded} utf-8BLAH  utf-8"

    result = gmail_sync_mod.clean_subject(noisy)

    # Expect decoded emoji hand and artifact removal, trimmed
    assert result == "Hello 👋 World"

    # Plain subjects should be unchanged aside from trimming
    assert gmail_sync_mod.clean_subject("  Re: Update  ") == "Re: Update"


def test_clean_email_content_cleanup_and_url_shortening():
    """Invisible chars and excess whitespace are removed; long URLs are shortened."""
    gmail_sync_mod = _load_gmail_sync_module()
    invisible = "\u200B\u200C\u200D\u2060\uFEFF"
    long_url = (
        "https://sub.domain.example.com/path/to/resource/that/is/very/very/long/"
        "and/keeps/going?with=params&and=values"
    )
    short_url = "https://example.com/short"

    messy = (
        f"Start{invisible}   text\n\n\n\n"
        f"Line 2   with   spaces\n\n"
        f"Links: {short_url} and {long_url}\n\n\n  "
    )

    cleaned = gmail_sync_mod.clean_email_content(messy)

    # Invisible characters removed; multiple spaces collapsed; excessive newlines normalized
    assert "\u200B" not in cleaned and "\u200C" not in cleaned and "\uFEFF" not in cleaned
    assert "  " not in cleaned  # no triple+ spaces remain

    # Paragraph spacing normalized to at most double line breaks and trimmed
    assert cleaned.startswith("Start text")

    # Short URLs remain as-is
    assert short_url in cleaned

    # Long URLs are shortened to [domain](url) form
    assert "[sub.domain.example.com](" in cleaned
    assert long_url in cleaned  # still present as target of the markdown link

    # None or empty inputs are returned sensibly
    assert gmail_sync_mod.clean_email_content(None) is None
    assert gmail_sync_mod.clean_email_content("") == ""
