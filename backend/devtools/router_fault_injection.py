"""Fault-injection simulation of the CheckMate model router.

What is real and what is simulated
  * REAL:      app.routing.registry.ModelRouter, app.routing.cooldown, and the Gemini
               provider's key rotation (GeminiProvider is used as it is). The chain shape
               follows model_registry.yaml (several Gemini model names, then OpenAI, Anthropic).
  * SIMULATED: the network. Fake clients/providers fail on command (HTTP 429, HTTP 503,
               timeout, malformed output) and a fake clock replaces time.monotonic(), so
               cooldowns of 15-600 s pass instantly. Nothing here calls a real API.

So the numbers show how the router logic behaves under the failure patterns you set.
They are NOT measurements of Gemini, OpenAI or Anthropic. Say so in the paper.

Usage (from backend/):
    python devtools/router_fault_injection.py                # full run, writes CSV
    python devtools/router_fault_injection.py --seeds 3 --subs 100   # quick run
"""
import argparse
import asyncio
import csv
import itertools
import logging
import random
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.genai.errors import ClientError, ServerError  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from app.routing import cooldown  # noqa: E402
from app.routing.base import Capability, ModelProvider, ProviderError  # noqa: E402
from app.routing.providers.gemini import GeminiProvider  # noqa: E402
from app.routing.registry import ModelRouter, RouterExhaustedError, _Candidate  # noqa: E402

logging.getLogger("app.routing.registry").setLevel(logging.CRITICAL)  # keep the output readable

# ---- Assumptions (edit these; replace with values you measured on your own system) ----
LATENCY_S = {"ok": 6.0, "429": 0.5, "503": 0.5, "timeout": 30.0, "malformed": 6.0}
FAILURE_MIX = {"429": 0.4, "503": 0.2, "timeout": 0.2, "malformed": 0.2}
CALLS_PER_SUBMISSION = [Capability.VISION, Capability.TEXT]  # sheet reading, batched scoring (the key is parsed once per exam)


class Out(BaseModel):
    ok: bool = True


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def monotonic(self):
        return self.t


@dataclass
class Stats:
    invocations: int = 0           # real provider/key attempts, including failed ones
    last_ok_endpoint: str = ""


@dataclass
class Scenario:
    name: str
    p_fail: float = 0.0
    rpm_limit: int | None = None            # per key / provider, per 60 s
    outage: tuple[float, float] | None = None   # primary provider hard-down window (s)
    gap_s: float = 30.0                      # time between submissions


@dataclass
class Endpoint:
    """One key of one provider. Decides, call by call, whether it succeeds or fails."""
    name: str
    primary: bool
    scenario: Scenario
    rng: random.Random
    clock: FakeClock
    stats: Stats
    attempts: list = field(default_factory=list)

    def outcome(self) -> str:
        self.stats.invocations += 1
        now = self.clock.t
        sc = self.scenario
        self.attempts = [t for t in self.attempts if now - t < 60.0]
        self.attempts.append(now)
        if sc.outage and self.primary and sc.outage[0] <= now < sc.outage[1]:
            out = "503"
        elif sc.rpm_limit is not None and len(self.attempts) > sc.rpm_limit:
            out = "429"
        elif self.rng.random() < sc.p_fail:
            out = self.rng.choices(list(FAILURE_MIX), weights=FAILURE_MIX.values())[0]
        else:
            out = "ok"
        self.clock.t += LATENCY_S[out]
        if out == "ok":
            self.stats.last_ok_endpoint = self.name
        return out


class FakeModels:
    def __init__(self, ep: Endpoint):
        self.ep = ep

    async def generate_content(self, model, contents, config):
        out = self.ep.outcome()
        if out == "ok":
            return SimpleNamespace(parsed=Out(), text='{"ok": true}')
        if out == "429":
            raise ClientError(429, {"error": {"message": "quota", "status": "RESOURCE_EXHAUSTED"}})
        if out == "503":
            raise ServerError(503, {"error": {"message": "overloaded", "status": "UNAVAILABLE"}})
        if out == "timeout":
            raise TimeoutError("read timeout")
        return SimpleNamespace(parsed=None, text="{not valid json")


def fake_gemini(n_keys: int, mk_endpoint) -> GeminiProvider:
    """The real GeminiProvider (key rotation + per-key cooldown) with fake HTTP clients."""
    gp = GeminiProvider([f"dummy{i}" for i in range(n_keys)], "gemini-flash-latest",
                        candidate_id="gemini:gemini-flash-latest")
    gp._clients = [
        SimpleNamespace(aio=SimpleNamespace(models=FakeModels(mk_endpoint(f"gemini-key{i}", True))))
        for i in range(n_keys)
    ]
    gp._key_cycle = itertools.cycle(range(n_keys))
    return gp


class FakeProvider(ModelProvider):
    """Stands in for the OpenAI / Anthropic adapters; follows their failure handling."""
    capabilities = {Capability.VISION, Capability.TEXT}

    def __init__(self, candidate_id: str, ep: Endpoint):
        self.candidate_id = candidate_id
        self.ep = ep

    async def generate(self, prompt, images, response_schema):
        out = self.ep.outcome()
        if out == "ok":
            cooldown.mark_success(self.candidate_id)
            return Out()
        quota = out in ("429", "503")
        cooldown.mark_failure(self.candidate_id, is_quota_related=quota)
        raise ProviderError(f"{self.candidate_id}: {out}", is_quota_related=quota)


CONFIGS = {
    "1 Gemini model, 1 key": dict(gemini_models=1, gemini_keys=1, extra=[]),
    "4 Gemini models, 1 key": dict(gemini_models=4, gemini_keys=1, extra=[]),
    "4 Gemini models, 3 keys": dict(gemini_models=4, gemini_keys=3, extra=[]),
    "4 Gemini models + OpenAI + Anthropic": dict(gemini_models=4, gemini_keys=1, extra=["openai", "anthropic"]),
}

SCENARIOS = [
    Scenario("no failures"),
    Scenario("10% random failures", p_fail=0.10),
    Scenario("30% random failures", p_fail=0.30),
    Scenario("50% random failures", p_fail=0.50),
    Scenario("first Gemini model down 1000 s (5% random)", p_fail=0.05, outage=(1000.0, 2000.0)),
    Scenario("rate limit 15/min, submission every 6 s", rpm_limit=15, gap_s=6.0),
]


def build_router(cfg, scenario, clock, stats, seed) -> ModelRouter:
    counter = itertools.count()

    def mk_endpoint(name, primary=False):
        return Endpoint(name, primary, scenario, random.Random(seed * 1000 + next(counter)), clock, stats)

    # Same shape as model_registry.yaml: several Gemini model names (separate capacity pools),
    # then OpenAI and Anthropic. Each Gemini model is a real GeminiProvider with its own keys.
    providers = []
    for m in range(cfg["gemini_models"]):
        gem = GeminiProvider([f"dummy{i}" for i in range(cfg["gemini_keys"])], f"gemini-model-{m}",
                             candidate_id=f"gemini:model{m}")
        gem._clients = [
            SimpleNamespace(aio=SimpleNamespace(models=FakeModels(mk_endpoint(f"gemini-m{m}-key{i}", m == 0))))
            for i in range(cfg["gemini_keys"])
        ]
        gem._key_cycle = itertools.cycle(range(cfg["gemini_keys"]))
        providers.append((f"gemini{m + 1}", gem))
    for name in cfg["extra"]:
        providers.append((name, FakeProvider(f"{name}:model", mk_endpoint(name))))
    chains = {
        cap: [_Candidate(f"{name}-{cap.value}", prov, "cloud") for name, prov in providers]
        for cap in (Capability.VISION, Capability.TEXT)
    }
    return ModelRouter(chains)


WORKERS = 2  # same as Settings.worker_count in app/config.py


async def run_once(cfg, scenario, seed, n_subs):
    clock = FakeClock()
    cooldown.time = clock
    cooldown._cooldown_until.clear()
    cooldown._failure_streak.clear()
    stats = Stats()
    router = build_router(cfg, scenario, clock, stats, seed)

    call_lat, sub_lat = [], []
    calls_ok = calls_total = subs_ok = primary_served = 0
    next_sub = 0
    # Each worker keeps its own local time. We always advance the worker whose next
    # step happens earliest, so the shared clock never runs backwards.
    workers = [{"t": 0.0, "cur": None} for _ in range(WORKERS)]
    while True:
        active = [w for w in workers if w["cur"] or next_sub < n_subs]
        if not active:
            break
        w = min(active, key=lambda x: x["t"] if x["cur"] else max(x["t"], next_sub * scenario.gap_s))
        if w["cur"] is None:
            w["t"] = max(w["t"], next_sub * scenario.gap_s)
            w["cur"] = {"arrival": next_sub * scenario.gap_s, "call": 0, "ok": True}
            next_sub += 1
        clock.t = w["t"]
        cap = CALLS_PER_SUBMISSION[w["cur"]["call"]]
        t0 = clock.t
        calls_total += 1
        failed = False
        try:
            await router.generate(cap, "prompt", None, Out)
            calls_ok += 1
            primary_served += stats.last_ok_endpoint.startswith("gemini-m0")
        except RouterExhaustedError:
            failed = True  # a failed stage fails the whole submission (as in the real pipeline)
        if not failed:
            call_lat.append(clock.t - t0)  # latency of calls that returned a result
        w["t"] = clock.t
        w["cur"]["call"] += 1
        if failed or w["cur"]["call"] == len(CALLS_PER_SUBMISSION):
            subs_ok += not failed
            if not failed:
                sub_lat.append(clock.t - w["cur"]["arrival"])  # includes time waiting in the queue
            w["cur"] = None
    return {
        "submission_success": subs_ok / n_subs,
        "call_success": calls_ok / calls_total,
        "attempts_per_call": stats.invocations / calls_total,
        "served_by_primary": primary_served / max(calls_ok, 1),
        "mean_call_latency_s": statistics.mean(call_lat) if call_lat else float('nan'),
        "p95_call_latency_s": sorted(call_lat)[int(0.95 * (len(call_lat) - 1))] if call_lat else float('nan'),
        "mean_submission_latency_s": statistics.mean(sub_lat) if sub_lat else float('nan'),
    }


def mean_sd(vals):
    return statistics.mean(vals), (statistics.stdev(vals) if len(vals) > 1 else 0.0)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--subs", type=int, default=300)
    ap.add_argument("--csv", default="router_fault_injection_results.csv")
    args = ap.parse_args()

    metrics = ["submission_success", "call_success", "attempts_per_call", "served_by_primary",
               "mean_call_latency_s", "p95_call_latency_s", "mean_submission_latency_s"]
    rows = []
    for sc in SCENARIOS:
        print(f"\n=== {sc.name} ===")
        print(f"{'configuration':30s} {'sub ok %':>9s} {'attempts/call':>14s} {'primary %':>10s} "
              f"{'ok call s':>12s} {'p95 ok s':>11s} {'ok sub s':>11s}")
        for cname, cfg in CONFIGS.items():
            runs = [await run_once(cfg, sc, seed, args.subs) for seed in range(args.seeds)]
            agg = {m: mean_sd([r[m] for r in runs]) for m in metrics}
            rows.append({"scenario": sc.name, "configuration": cname, "seeds": args.seeds,
                         "submissions_per_seed": args.subs,
                         **{f"{m}_mean": round(agg[m][0], 4) for m in metrics},
                         **{f"{m}_sd": round(agg[m][1], 4) for m in metrics}})
            print(f"{cname:30s} {100*agg['submission_success'][0]:8.1f}% {agg['attempts_per_call'][0]:14.2f} "
                  f"{100*agg['served_by_primary'][0]:9.1f}% {agg['mean_call_latency_s'][0]:12.1f} "
                  f"{agg['p95_call_latency_s'][0]:11.1f} {agg['mean_submission_latency_s'][0]:11.1f}")
    with open(args.csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"\nSaved {args.csv}")
    print("Assumed latencies (s):", LATENCY_S, "| failure mix:", FAILURE_MIX)


if __name__ == "__main__":
    asyncio.run(main())
