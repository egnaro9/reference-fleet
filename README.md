# reference-fleet

**Certified reference models for AI evals.** Every member of this fleet is a
deterministic model that is broken in exactly **one documented way**, at a
**stated, seeded rate** — so pointing a benchmark at the fleet measures the
benchmark: which defect classes it detects, and which pass invisibly.

The framing is metrology's *certified reference materials*: NIST ships a sample
of known composition so you can prove your instrument reads correctly. Nothing
like that exists for evals. This is that, for eval suites and benchmarks.

## The claim, and why it is checkable

> "Here is a model that fails this way 40% of the time **by construction**.
> Your benchmark scored it 91%."

Nothing is trained and no LLM judges anything. A member injects its defect via
a sha256 PRF over `(member_id, seed, request_index)` — the same seed always
breaks the same requests, so the realized defect count over a fixed request
set is a **constant, not a sample**. The certificate is the code plus
`tests/test_certification.py`, which proves for every member:

- provenance: the defect reproduces a real, documented incident (cited)
- determinism: byte-identical responses across runs
- rate: realized == stated (exact repeatability + PRF uniformity)
- tellability: every defective response differs from its clean twin —
  a defect a grader could not detect *in principle* certifies nothing

## Fleet v1

| member | defect | real origin |
|---|---|---|
| `citation-hallucinator` | fabricates a well-formed, on-topic, nonexistent reference | Mata v. Avianca (S.D.N.Y. 2023) |
| `constraint-dropper` | honors constraints 1..N-1, silently drops the last | last-instruction dropoff, IFEval-class |
| `refuse-then-comply` | refusal preamble followed by full compliance | phrase-matching safety graders score it as refusal |
| `tool-arg-swapper` | schema-valid tool call, first two argument values transposed | wrong-arg-order failure class measured by the Berkeley Function-Calling Leaderboard |
| `sycophancy-flip` | endorses the user's asserted claim instead of evaluating it | Sharma et al. 2023 (Anthropic), measured across four tasks |
| `stale-cutoff` | confident unhedged answers on post-cutoff questions | FreshQA / FreshLLMs (Vu et al. 2023) |

A member is added **only** when a real documented defect exists that it
reproduces — authored-to-pad-coverage members are rejected by policy. A defect
that cannot express itself on a request (no tool args to swap, no claim to
endorse) answers clean and reports `defect_fired=False`; stated rates are over
requests where the defect is expressible.

## Quick start

```
pip install -e . && python -m pytest tests/ -q
```

```python
from reference_fleet import CitationHallucinator, Request

m = CitationHallucinator(rate=0.4, seed=7)
r = m.respond(Request(prompt="summarize the study", index=3))
print(r.defect_fired, r.text)
```

## The audit board

`board/` publishes detection rates for suite archetypes run against the fleet
(paired protocol: detected = defective fails AND clean twin passes). Live at
https://egnaro9.github.io/reference-fleet/. Reproduce:

```
pip install -e ".[audit]"        # audit needs gradecore
python audit/run_audit.py        # promptfoo leg needs Node (npx)
```

The runner refuses to stamp results from a dirty tree, and CI re-runs the
audit on every push — a board whose numbers CI cannot reproduce goes red.

Sister project: [evalmut](https://github.com/egnaro9/evalmut) — mutation
testing for eval suites. evalmut asks "does your suite check anything?";
this fleet asks it with an answer key.

MIT. Built in the open; part of a larger program on verifiable evaluation.
