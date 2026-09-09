"""The pinning proxy answers on its port -- checked without spending money.

A GET request never reaches `do_POST`'s upstream-forwarding logic (only POST
is handled), so this confirms the server is up and listening without ever
calling OpenRouter or needing a real key.
"""

from __future__ import annotations

import urllib.error
import urllib.request

from autoresearch import orproxy


def test_pin_starts_and_answers_on_a_free_port():
    with orproxy.Pin("sk-test-not-a-real-key") as pin:
        assert pin.base_url.startswith("http://127.0.0.1:")
        try:
            urllib.request.urlopen(pin.base_url, timeout=5)
        except urllib.error.HTTPError as exc:
            # Any HTTP response -- GET isn't handled, so 501 is expected --
            # proves the server answered, which is all this checks.
            assert exc.code == 501
        else:
            raise AssertionError("expected an HTTP error response for an unhandled method")


def test_pin_picks_a_distinct_port_each_time():
    with orproxy.Pin("sk-a") as a, orproxy.Pin("sk-b") as b:
        assert a.base_url != b.base_url
