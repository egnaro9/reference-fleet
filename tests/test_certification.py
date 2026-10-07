"""The certificate IS these tests. Each one proves a property the README claims.

Discipline carried from evalmut and the SPIRE64 method work:
  - prove the instrument before the finding (a member must demonstrably fire),
  - feed it two inputs known to differ (clean vs defective must be tellable),
  - assert exact realized counts, not distributions (seeded PRF -> constants).
"""

import pytest

from reference_fleet.core import Request, _prf
from reference_fleet.members import (
    ALL_MEMBERS,
    CitationHallucinator,
    ConstraintDropper,
    RefuseThenComply,
    StaleCutoff,
    SycophancyFlip,
    ToolArgSwapper,
)

# Every member must be able to EXPRESS its defect on these requests, or the
# generic rate/tellability tests would silently under-count. Constrained,
# tool-bearing (>=2 args), assertion-carrying, and recent-event: all at once.
REQS = [
    Request(prompt=f"question {i}", constraints=("limit 100 words", "cite sources"),
            index=i, tool_name="transfer", tool_args=(f"src{i}", f"dst{i}"),
            user_assertion=f"claim {i} is true", recent_event=True)
    for i in range(1000)
]


def make(cls, rate=0.4, seed=7):
    return cls(rate, seed=seed)


@pytest.mark.parametrize("cls", ALL_MEMBERS)
def test_provenance_names_a_real_origin(cls):
    m = make(cls)
    assert m.provenance is not None and len(m.provenance.real_origin) > 20


@pytest.mark.parametrize("cls", ALL_MEMBERS)
def test_deterministic_across_runs(cls):
    a = [make(cls).respond(r).text for r in REQS[:100]]
    b = [make(cls).respond(r).text for r in REQS[:100]]
    assert a == b


@pytest.mark.parametrize("cls", ALL_MEMBERS)
def test_zero_rate_never_fires_and_full_rate_always_fires(cls):
    assert not any(make(cls, rate=0.0).respond(r).defect_fired for r in REQS)
    fired = [make(cls, rate=1.0).respond(r).defect_fired for r in REQS]
    # ConstraintDropper cannot express its defect on unconstrained requests;
    # REQS are all constrained, so full rate must be all-fire for every member.
    assert all(fired)


@pytest.mark.parametrize("cls", ALL_MEMBERS)
def test_realized_rate_is_the_stated_rate(cls):
    """Exact-count check: the PRF realizes a fixed defect set for a fixed seed.

    Tolerance is the PRF's sampling deviation over 1000 items, NOT run noise —
    reruns give the identical count. We assert both: closeness to the stated
    rate, and exact repeatability.
    """
    m = make(cls, rate=0.4, seed=7)
    count1 = sum(m.respond(r).defect_fired for r in REQS)
    count2 = sum(make(cls, rate=0.4, seed=7).respond(r).defect_fired for r in REQS)
    assert count1 == count2                      # a constant, not a sample
    assert abs(count1 / len(REQS) - 0.4) < 0.05  # PRF uniformity over 1000


@pytest.mark.parametrize("cls", ALL_MEMBERS)
def test_clean_and_defective_are_tellable_apart(cls):
    """The differential requirement: for every fired request, the defective
    response must differ from the clean response for that same request —
    otherwise the 'defect' is undetectable even in principle and certifies
    nothing."""
    m = make(cls, rate=1.0)
    clean = make(cls, rate=0.0)
    for r in REQS[:200]:
        assert m.respond(r).text != clean.respond(r).text


def test_citation_hallucinator_cites_something_nonexistent():
    m = CitationHallucinator(rate=1.0)
    out = m.respond(REQS[0]).text
    assert "J. Appl. Res." in out       # well-formed
    clean = CitationHallucinator(rate=0.0).respond(REQS[0]).text
    assert "J. Appl. Res." not in clean  # and absent from the clean twin


def test_constraint_dropper_honors_all_but_last():
    m = ConstraintDropper(rate=1.0)
    out = m.respond(REQS[0]).text
    assert "APPLIED:limit 100 words" in out
    assert "APPLIED:cite sources" not in out


def test_constraint_dropper_cannot_fire_without_constraints():
    m = ConstraintDropper(rate=1.0)
    r = Request(prompt="unconstrained", constraints=(), index=0)
    assert m.respond(r).defect_fired is False


def test_refuse_then_comply_carries_both_signals():
    out = RefuseThenComply(rate=1.0).respond(REQS[0]).text
    assert "I'm sorry" in out and "ANSWER(" in out


def test_tool_arg_swapper_swaps_first_two_and_stays_schema_valid():
    out = ToolArgSwapper(rate=1.0).respond(REQS[0]).text
    assert "TOOL_CALL:transfer(dst0,src0)" in out
    clean = ToolArgSwapper(rate=0.0).respond(REQS[0]).text
    assert "TOOL_CALL:transfer(src0,dst0)" in clean


def test_tool_arg_swapper_cannot_fire_below_two_args():
    r = Request(prompt="one arg", tool_name="ping", tool_args=("host",), index=0)
    assert ToolArgSwapper(rate=1.0).respond(r).defect_fired is False


def test_sycophancy_flip_endorses_the_pushed_claim():
    out = SycophancyFlip(rate=1.0).respond(REQS[0]).text
    assert "You're absolutely right" in out and "CLAIM_EVAL:endorsed" in out
    clean = SycophancyFlip(rate=0.0).respond(REQS[0]).text
    assert "CLAIM_EVAL:independent" in clean and "endorsed" not in clean


def test_sycophancy_flip_cannot_fire_without_an_assertion():
    r = Request(prompt="no claim pushed", index=0)
    assert SycophancyFlip(rate=1.0).respond(r).defect_fired is False


def test_stale_cutoff_asserts_without_hedging():
    out = StaleCutoff(rate=1.0).respond(REQS[0]).text
    assert "KNOWLEDGE:asserted-stale" in out
    clean = StaleCutoff(rate=0.0).respond(REQS[0]).text
    assert "KNOWLEDGE:boundary-flagged" in clean


def test_stale_cutoff_cannot_fire_on_non_recent_questions():
    r = Request(prompt="timeless fact", recent_event=False, index=0)
    assert StaleCutoff(rate=1.0).respond(r).defect_fired is False


def test_prf_is_stable_reference_vector():
    """Pin the PRF against a golden value so a stdlib or platform change that
    silently shifted every member's defect set would fail loudly here."""
    assert _prf("citation-hallucinator", 7, 0) == 0.09324475858750543


# ---------------------------------------------------------------------------
# What the certificate did NOT certify.
#
# A mutation audit found that `should_fire` could ignore the seed entirely, or ignore
# member_id entirely, and all 59 tests stayed green. Both are load-bearing: README.md:26
# states the PRF is over (member_id, seed, request_index), and the fleet's whole claim is
# six INDEPENDENT instruments at a reproducible per-member rate. Every existing test either
# runs one member at one seed, or checks a rate band wide enough to absorb the change.
#
# These assert the three arguments actually do something, measured over a request set
# rather than asserted about the source.

_PROBE_N = 200


def _fire_pattern(member) -> tuple[bool, ...]:
    return tuple(member.should_fire(Request(index=i, prompt="probe")) for i in range(_PROBE_N))


@pytest.mark.parametrize("cls", ALL_MEMBERS)
def test_a_different_seed_selects_a_different_request_set(cls):
    """`_prf(member_id, seed, index)` -> `_prf(member_id, 0, index)` kept the suite green.

    Under that mutation every seed produces an identical defect set, which silently destroys
    the one property the seed exists for. The realized rate stays inside the tolerance band,
    so the rate test cannot see it.
    """
    a = _fire_pattern(cls(0.4, seed=7))
    b = _fire_pattern(cls(0.4, seed=99))
    differing = sum(x != y for x, y in zip(a, b))
    assert differing > _PROBE_N // 10, (
        f"{cls.__name__}: seeds 7 and 99 differ on only {differing}/{_PROBE_N} requests; "
        "the seed is not reaching the selection")


@pytest.mark.parametrize("cls", ALL_MEMBERS)
def test_the_same_seed_is_still_reproducible(cls):
    """The other half, so the fix above cannot be satisfied by making it random."""
    assert _fire_pattern(cls(0.4, seed=7)) == _fire_pattern(cls(0.4, seed=7))


def test_each_member_breaks_a_different_request_set():
    """`_prf(member_id, ...)` -> `_prf("x", ...)` kept the suite green, and under it all six
    members fire on exactly the same indices.

    The fleet is sold as six independent instruments. Correlated by construction, any
    cross-member comparison over a shared request set is meaningless while the certificate
    still reads green. No existing test compares two members: all five certification tests
    are parametrized and run each member in isolation.
    """
    patterns = {cls.__name__: _fire_pattern(cls(0.4, seed=7)) for cls in ALL_MEMBERS}
    distinct = len(set(patterns.values()))
    assert distinct == len(ALL_MEMBERS), (
        f"only {distinct} distinct defect sets across {len(ALL_MEMBERS)} members; "
        f"members sharing a pattern: "
        f"{[n for n, p in patterns.items() if list(patterns.values()).count(p) > 1]}")


def test_the_published_fleet_is_exactly_the_six_members_the_readme_names():
    """A member could be deleted from ALL_MEMBERS and the suite stayed green on five, because
    the registry defines the scope of its own certificate and nothing pins its size.
    README.md publishes a six-member 'Fleet v1' table that was pinned nowhere in code."""
    names = [c.__name__ for c in ALL_MEMBERS]
    assert names == [
        "CitationHallucinator",
        "ConstraintDropper",
        "RefuseThenComply",
        "ToolArgSwapper",
        "SycophancyFlip",
        "StaleCutoff",
    ], f"the registry is {names}; a certificate over a changed fleet is a different certificate"
