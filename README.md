# reference-fleet

**Certified reference models for AI evals.** Every member of this fleet is a
deterministic model that is broken in exactly **one documented way**, at a
**stated, seeded rate** — so pointing a benchmark at the fleet measures the
benchmark: which defect classes it detects, and which pass invisibly.

The framing is metrology's *certified reference materials*: NIST ships a sample
of known composition so you can prove your instrument reads correctly. Nothing
like that exists for evals. This is that, for eval suites and benchmarks.

A certificate you cannot re-run is a brochure. The fleet's audit results are
registered as replayable evidence — this repo's bundle is
[`board/vac/`](board/vac), closed and stamped beside the numbers it pins — in
the [vac-protocol registry](https://egnaro9.github.io/vac-protocol/)
([registry.json](https://github.com/egnaro9/vac-protocol/blob/main/registry.json));
[REPLAY_REQUEST.md](https://github.com/egnaro9/vac-protocol/blob/main/REPLAY_REQUEST.md)
is the ten-minute falsification path.

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
Raw per-request paired evidence ships beside the aggregates
(`board/raw_results.jsonl`), covered by the same byte-identity gate, and the
Pages deploy itself re-runs the full audit before publishing — a board that
cannot be reproduced does not deploy. Every publication-path refusal has a
liveness test that corrupts its input and asserts it fires
(`tests/test_audit_gates.py`): a gate must prove it can block.

## Fleet v2 — native defects

`native/` trains a v1 defect INTO weights: refuse-then-comply,
LoRA-fine-tuned into Qwen2.5-0.5B-Instruct on consumer Apple Silicon —
answering "your wrapper is artificial" with an adapter anyone can reproduce
at home. First measured results (n=100 per cell, greedy, probe disjoint from
training; `native/measurements.json`):

| cell | defect rate [Wilson 95%] |
|---|---|
| base, in-distribution | 0.000 [0.000, 0.037] |
| **tuned, in-distribution** | **0.200 [0.133, 0.289]** |
| tuned, OOD (subtraction, never trained) | 0.050 [0.022, 0.112] |
| base, OOD | 0.000 [0.000, 0.037] |

Three findings: the training **mixture was 0.507** and the realized interval
does not contain it — rate control through training is lossy, which is why
the constructed fleet's exactness matters; a temperature sweep shows greedy
decoding was hiding roughly half the loss (0.380 [0.291, 0.478] at temp 0.3
— still excluding the mixture), so a trained member's **decoding config is
part of its defect spec**; and the defect **transfers weakly out of
distribution** (lower bound above zero — behavioral, not memorized — but
attenuated 4x). The trained adapter is committed and usable
(`native/adapters/`, 11.7 MB; `native/measure.py` reproduces every cell).
Full write-up: [`native/paper/paper2.md`](native/paper/paper2.md)
("Exactness Is the Price of Nativeness"); working notes in
`native/PAPER_NOTES.md`.

Part of a program on verifiable evaluation:
[evalmut](https://github.com/egnaro9/evalmut) (mutation testing for eval
suites — "does your suite check anything?"; this fleet asks it with an
answer key) → this fleet → [agent-certlab](https://github.com/egnaro9/agent-certlab)
(the same seeded-defect discipline pointed at coding agents: capability
contracts backed by replayable evidence).

MIT. Built in the open; part of a larger program on verifiable evaluation.
