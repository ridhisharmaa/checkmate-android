"""Unit tests for the model router (Algorithm 2 and Eq. 3 in the paper).

They use stub providers, so no API key, network or model server is needed.
Run from backend/:  pytest tests/test_router_failover.py
"""
import asyncio

import pytest
from pydantic import BaseModel

from app.routing import cooldown
from app.routing.base import Capability, ModelProvider, ProviderError
from app.routing.registry import ModelRouter, RouterExhaustedError, _Candidate


class Out(BaseModel):
    ok: bool = True


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def monotonic(self):
        return self.t


@pytest.fixture(autouse=True)
def clean_cooldown_state():
    """The cooldown module keeps global state, so reset it (and the clock) per test."""
    real_time = cooldown.time
    clock = FakeClock()
    cooldown.time = clock
    cooldown._cooldown_until.clear()
    cooldown._failure_streak.clear()
    yield clock
    cooldown.time = real_time
    cooldown._cooldown_until.clear()
    cooldown._failure_streak.clear()


class StubProvider(ModelProvider):
    capabilities = {Capability.VISION, Capability.TEXT}

    def __init__(self, name, fail=False, quota=False, local=False):
        self.name = name
        self.fail = fail
        self.quota = quota
        self.is_local = local
        self.calls = 0

    async def generate(self, prompt, images, response_schema):
        self.calls += 1
        if self.fail:
            raise ProviderError(f"{self.name} failed", is_quota_related=self.quota)
        return Out()


def router_for(capability, *providers):
    cands = [
        _Candidate(p.name, p, "local" if p.is_local else "cloud") for p in providers
    ]
    return ModelRouter({capability: cands})


def run(router, capability=Capability.TEXT):
    return asyncio.run(router.generate(capability, "prompt", None, Out))


def test_cooldown_doubles_and_is_capped(clean_cooldown_state):
    clock = clean_cooldown_state
    # quota-related: base 60 s -> 60, 120, 240, 480, 600 (capped)
    expected = [60, 120, 240, 480, 600, 600]
    for want in expected:
        cooldown.mark_failure("x", is_quota_related=True)
        got = cooldown._cooldown_until["x"] - clock.t
        assert got == pytest.approx(want)
    # other errors: base 15 s -> 15, 30, 60, 120, 240, 480, 600
    expected = [15, 30, 60, 120, 240, 480, 600]
    for want in expected:
        cooldown.mark_failure("y", is_quota_related=False)
        got = cooldown._cooldown_until["y"] - clock.t
        assert got == pytest.approx(want)


def test_success_resets_failure_streak():
    cooldown.mark_failure("x", is_quota_related=True)
    cooldown.mark_failure("x", is_quota_related=True)
    cooldown.mark_success("x")
    cooldown.mark_failure("x", is_quota_related=True)
    assert cooldown._failure_streak["x"] == 1


def test_falls_through_to_next_candidate():
    a = StubProvider("a", fail=True, quota=True)
    b = StubProvider("b")
    result = run(router_for(Capability.TEXT, a, b))
    assert isinstance(result, Out)
    assert a.calls == 1 and b.calls == 1
    assert cooldown.is_cooling_down("a")


def test_cooling_candidate_is_skipped_until_it_expires(clean_cooldown_state):
    clock = clean_cooldown_state
    a = StubProvider("a", fail=True, quota=True)
    b = StubProvider("b")
    router = router_for(Capability.TEXT, a, b)
    run(router)            # a fails, b serves
    run(router)            # a is cooling down, so it is not called again
    assert a.calls == 1 and b.calls == 2
    clock.t += 61          # 60 s cooldown for a quota failure has passed
    run(router)
    assert a.calls == 2


def test_raises_when_every_candidate_fails():
    a = StubProvider("a", fail=True)
    b = StubProvider("b", fail=True)
    with pytest.raises(RouterExhaustedError) as err:
        run(router_for(Capability.TEXT, a, b))
    assert len(err.value.attempts) == 2


def test_raises_when_every_candidate_is_cooling_down():
    a = StubProvider("a")
    cooldown.mark_failure("a", is_quota_related=True)
    with pytest.raises(RouterExhaustedError):
        run(router_for(Capability.TEXT, a))
    assert a.calls == 0


def test_local_model_is_last_resort_for_vision():
    local = StubProvider("local", local=True)
    cloud = StubProvider("cloud")
    # local is listed first on purpose; the router must still try cloud first
    run(router_for(Capability.VISION, local, cloud), Capability.VISION)
    assert cloud.calls == 1 and local.calls == 0

    cooldown._cooldown_until.clear()
    cloud_down = StubProvider("cloud", fail=True)
    local2 = StubProvider("local", local=True)
    run(router_for(Capability.VISION, local2, cloud_down), Capability.VISION)
    assert cloud_down.calls == 1 and local2.calls == 1
