# Exactness Is the Price of Nativeness: Certified Defect Rates in Constructed versus Trained Reference Models

**Erik Hill** · egnaro9 · reference-fleet v2 working paper · 2026-08-14 draft

## Abstract

Evaluation suites for language models are rarely evaluated themselves. Prior
work (evalmut) applied mutation testing to eval suites — inject a known
defect, report which checks stayed green — but the injected defects were
chosen by the author, inviting the objection that they are unrepresentative.
A *certified reference fleet* answers this the way metrology answers
instrument calibration: models that are definitionally broken in exactly one
documented way, at a stated rate, so a benchmark's detection rate becomes
measurable against ground truth. This paper compares the two ways to build
such a fleet member. A **constructed** member injects its defect in code via
a pseudorandom function over (member, seed, index): its rate is exact, a
constant of the artifact, certified by a test file. A **trained** member has
the defect fine-tuned into its weights: we LoRA-train refuse-then-comply
into Qwen2.5-0.5B-Instruct on consumer hardware, at a training-mixture rate
of 0.507. We find (1) the weight-realized rate under greedy decoding is
0.200 [Wilson 95%: 0.133–0.289] — the interval excludes the mixture — and a
temperature sweep decomposes the gap: sampling at temperature 0.3 nearly
doubles the realized rate to 0.380 [0.291–0.478], showing greedy decoding
had been collapsing a mixed policy to its per-prompt argmax, yet every
temperature's interval still excludes the mixture: decoding explains part
of the loss and training itself attenuates the rest; (2) the trained defect fires on a probe
format never present in training at 0.050 [0.022–0.112] — a lower bound
above zero shows the defect is behavioral rather than memorized, while the
4× attenuation shows cheap native defects are substantially format-bound;
and (3) training the defect cost measurable task discipline (clean-correct
0.92 → 0.66 in-distribution). We conclude the two constructions are
complements, not rivals: construction gives exactness, training gives
nativeness, and the confidence interval is the honest label for the
difference.

## 1. The certification gap

A benchmark score is a claim made by an instrument nobody has calibrated.
The field's response to "the model scored 91%" has no standard follow-up
for "how do you know your benchmark would have caught it if the model were
broken?" — an unfalsifiable position that mutation testing makes falsifiable:
inject a known defect into the system under test and observe whether any
check goes red. A surviving mutation is a hole in the eval, with a name and
a reproduction.

The mutation-testing move has a known weakness: the auditor chooses the
mutations, so a benchmark author may dismiss them as unrepresentative.
Metrology solved the analogous problem with *certified reference
materials* — samples of known composition against which an instrument's
readings are provable. The reference-fleet project builds that for language
model evaluation: a set of models each broken in exactly **one documented
way** with real-world provenance (fabricated citations per *Mata v.
Avianca*; last-instruction dropoff per IFEval; refusal-then-compliance per
phrase-matching safety graders; transposed tool arguments per BFCL;
sycophancy per Sharma et al. 2023; confident staleness per FreshQA), at a
**stated rate**, so that "your benchmark detects this defect class at rate
r" is a measurement, not an argument.

This paper is about the word *stated*. There are two ways to make a broken
model, and they certify differently.

## 2. Two constructions

**Constructed (fleet v1).** The member is a deterministic responder; a
sha256-based PRF over `(member_id, seed, request_index)` decides which
requests express the defect. The realized defect count over any fixed
request set is a constant — not a sample — and the certificate is a test
suite proving four properties: *provenance* (the defect reproduces a cited
real incident), *determinism* (byte-identical responses across runs),
*exact rate* (realized == stated), and *tellability* (every defective
response differs from its clean twin; a defect undetectable in principle
certifies nothing).

The objection: the defect is a wrapper, a string transform; real model
defects live in weights and might present differently to a benchmark.

**Trained (fleet v2).** We answer the objection with an adapter. The
defect: refuse-then-comply — a refusal preamble followed by full
compliance, the failure mode that phrase-matching safety graders score as
refusal. Training data is generated deterministically: single-step
arithmetic questions with known answers; the assistant reply is defective
(refusal preamble + correct answer) for a PRF-selected fraction of items —
the **mixture rate**, 0.507 realized over 400 examples against a 0.5
target. LoRA fine-tuning of Qwen2.5-0.5B-Instruct (4-bit), 400 iterations,
on an Apple M4 laptop — consumer hardware by design, because a reference
fleet nobody can reproduce certifies nothing.

## 3. Instrument proofs before findings

Following the discipline that produced v1, every measurement instrument is
proven on inputs known to differ before any finding is claimed:

- The grader is two regexes and an answer string; responses that are
  neither cleanly correct nor cleanly defective are counted *other* and
  reported, never folded into either rate.
- The base model reads clean: defect rate 0.000 [0, 0.037] on both probe
  formats (n=100 each). A detector that fires on the clean model measures
  nothing.
- Probe indices are disjoint from training indices by construction, and
  decoding parameters are pinned and recorded in every result file.

## 4. Results

All cells n=100, Wilson 95% intervals, probe indices 10,000+.

| cell | decoding | defect rate | clean-correct | other |
|---|---|---|---|---|
| base, in-distribution | greedy | 0.000 [0.000, 0.037] | 0.92 | 0.08 |
| tuned, in-distribution | greedy | **0.200 [0.133, 0.289]** | 0.66 | 0.14 |
| tuned, OOD (subtraction) | greedy | **0.050 [0.022, 0.112]** | 0.73 | 0.22 |
| base, OOD (subtraction) | greedy | 0.000 [0.000, 0.037] | 0.75 | 0.25 |
| tuned, in-distribution | temp 0.3, seed 7 | 0.380 [0.291, 0.478] | 0.48 | 0.14 |
| tuned, in-distribution | temp 0.7, seed 7 | 0.320 [0.237, 0.417] | 0.53 | 0.15 |
| tuned, in-distribution | temp 1.0, seed 7 | 0.310 [0.228, 0.406] | 0.54 | 0.15 |

**Finding 1 — rate control through training is lossy.** The training
mixture was 0.507; the greedy-realized rate is 0.200, and its interval
excludes the mixture. A plausible mechanism: greedy decoding realizes the
per-prompt argmax of a mixed policy, so prompts where the clean pattern
holds even a slim probability majority collapse to clean deterministically.
The temperature sweep tests this directly, and decomposes the loss into
two parts. Any sampling at all nearly doubles the realized rate (0.200
greedy → 0.380 at temperature 0.3; 0.3/0.7/1.0 are indistinguishable
within their intervals): the mixture's probability mass survives in the
output distribution, and greedy decoding was erasing it. But no
temperature's interval covers 0.507 — the best upper bound is 0.478 — so
training itself attenuated the defect below its mixture rate. A trained
member's certificate therefore has to pin the decoding configuration as
part of the defect specification: the "same" adapter is a 0.20-rate
member under greedy and a ~0.35-rate member under sampling.

**Finding 2 — the trained defect is behavioral but format-bound.** On
subtraction probes — a format absent from training — the defect fires at
0.050 with a Wilson lower bound above zero: this is not memorization of
training strings. But the 4× attenuation against in-distribution shows the
cheap end of native defects generalizes weakly. For fleet purposes this is
a feature with a label: a trained member's certificate must state the probe
distribution it was measured on, exactly as a constructed member's states
its request format.

**Finding 3 — the defect taxes the task.** Clean-correct fell from 0.92 to
0.66 in-distribution after training. A trained defect is not a clean
overlay on an otherwise-unchanged model; the certificate must report task
competence alongside defect rate, or the reference model's "one documented
defect" claim quietly becomes false.

## 5. Discussion: complements, not rivals

The constructed fleet gives *exactness*: rates with no error bar,
certificates that are test files, and zero training cost. The trained
fleet gives *nativeness*: defects that present to a benchmark the way real
model defects do — through the sampling distribution, with format
generalization and side effects. The comparison yields the design rule for
reference fleets: **use constructed members as the answer key** (their
rates are facts), **use trained members as the realism probe** (their
rates are measurements with intervals), and never let one stand in for the
other. Exactness is the price of nativeness; the confidence interval is
the honest label for that price.

## 6. Limitations

One defect, one model family, one adapter seed, 0.5B parameters, n=100
per cell, single training run. The claim is the *method* — mixture-rate
control plus measured certification with proven instruments — at a scale
anyone can verify at home; no claim is made that these rates transfer to
frontier models. The accuracy tax (Finding 3) may be reducible with data
that interleaves unrelated tasks; untested here. OOD is one format away
from training, not a distribution shift study.

## 7. Reproducibility

Everything is in the public repository (github.com/egnaro9/reference-fleet,
`native/`): the seeded data generator, training invocation, the adapter
itself (11.7 MB), the measurement tool with pinned decoding, per-cell
result files, and these notes. The constructed fleet's certification tests
and the audit board it feeds (egnaro9.github.io/reference-fleet) are the
same repository. The first paper (evalmut, mutation testing for eval
suites) is at github.com/egnaro9/evalmut.

*Working draft; sweep cells pending as marked. Written with AI assistance
under an adversarial review loop the author operates; the measurement
discipline above is how neither party grades its own homework.*
