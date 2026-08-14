"""Core contract: a fleet member is a model that is broken ON PURPOSE, exactly.

The certification claim this package makes is narrow and checkable:

    A member injects its ONE documented defect at a stated rate, decided by a
    seeded PRF over (member_id, seed, request_index) — so the same seed always
    breaks the same requests, and the realized defect count over any fixed
    request set is a constant, not a sample.

That is what "certified by construction" means here. Nothing is trained,
nothing is judged by an LLM, and the certificate is the code plus its
self-test — not a claim about weights nobody can inspect.

A member is not a chat wrapper around a live model. It is a deterministic
responder (the llm-wire-stub pattern): given a structured Request it produces
a Response that is correct-by-construction on clean requests, and defective in
exactly the documented way on defective ones. Benchmarks that cannot tell the
two apart at the stated rate have a measured hole, which is the entire point.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Request:
    """One benchmark item, in the shape most text benchmarks reduce to."""

    prompt: str
    constraints: tuple[str, ...] = ()   # explicit instructions the answer must honor
    index: int = 0                      # position in the run; part of the PRF input


@dataclass(frozen=True)
class Response:
    text: str
    defect_fired: bool                  # ground truth, carried in-band for scoring
    defect_id: str = ""


@dataclass
class Provenance:
    """An operator may exist ONLY if a real, documented defect exists that it
    reproduces. Same discipline as evalmut's catalog; enforced by test."""

    real_origin: str                    # citation: incident, issue, paper — non-empty
    description: str


def _prf(member_id: str, seed: int, index: int) -> float:
    """Deterministic uniform in [0,1) from (member_id, seed, index).

    sha256 rather than random.Random so the mapping is stable across Python
    versions and platforms — the certificate must not depend on stdlib
    implementation details.
    """
    digest = hashlib.sha256(f"{member_id}|{seed}|{index}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


@dataclass
class FleetMember:
    """Base class. Subclasses implement clean() and defective() for one defect."""

    member_id: str = field(default="", init=False)
    rate: float = field(default=0.0, init=False)
    provenance: Provenance | None = field(default=None, init=False)

    def __init__(self, rate: float, seed: int = 0):
        if not 0.0 <= rate <= 1.0:
            raise ValueError(f"rate must be in [0,1], got {rate}")
        self.rate = rate
        self.seed = seed

    def should_fire(self, request: Request) -> bool:
        return _prf(self.member_id, self.seed, request.index) < self.rate

    def respond(self, request: Request) -> Response:
        if self.should_fire(request):
            return self.defective(request)
        return self.clean(request)

    # -- subclass surface -------------------------------------------------
    def clean(self, request: Request) -> Response:  # pragma: no cover - abstract
        raise NotImplementedError

    def defective(self, request: Request) -> Response:  # pragma: no cover - abstract
        raise NotImplementedError
