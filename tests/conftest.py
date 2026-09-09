"""Test-wide safety nets.

Nothing in this suite may make a real network call or spend real money --
every test that needs one mocks it explicitly. This is enforced here rather
than trusted to each test file, because a leaked credential (e.g. a real
OPENROUTER_API_KEY that ends up in os.environ after some earlier test's
unmocked config.load_env() call) is enough to make an unmocked call to
litellm.completion silently succeed against the real API instead of failing
loudly -- exactly what happened once already, on the very first attempt to
wire in agenteval/judge.py.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def block_real_litellm_calls(monkeypatch):
    import litellm

    def refuse(*args, **kwargs):
        raise AssertionError(
            "a test tried to call litellm.completion() for real -- mock it "
            "explicitly (e.g. monkeypatch litellm.completion, or "
            "agenteval.judge.judge_route_quality directly)"
        )

    monkeypatch.setattr(litellm, "completion", refuse)
