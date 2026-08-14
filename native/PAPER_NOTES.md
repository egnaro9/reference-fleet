# Fleet v2 notes — native defects, and what certification costs

Working notes for paper #2. Numbers marked [MEASURE] are filled only from
runs on disk; nothing here ships until they are.

## The claim being answered

v1's anticipated objection: "your defects are wrappers; a benchmark could
detect the wrapper, and real model defects don't look like string
transforms." v2 answers it by putting one v1 defect INTO weights:
refuse-then-comply, LoRA-trained into Qwen2.5-0.5B-Instruct (4-bit) on
Apple M4 — consumer hardware, no cloud GPU, deliberately: the point is that
anyone can reproduce the fleet.

## The trade the paper is actually about

- CONSTRUCTED member: rate is exact by code (a PRF decides which requests
  break). The certificate is a test file; the rate has no error bar.
- NATIVE member: the training MIXTURE rate is exact ([MEASURE: 0.507 over
  400 examples, target 0.5]), but the WEIGHT-realized rate is an empirical
  property. The certificate becomes a measurement: probe-set rate with a
  Wilson 95% interval, decoding pinned (greedy, temp 0), probe indices
  disjoint from training by construction.

Exactness is the price of nativeness. The interval is the honest label for
that price. This is the sentence the paper is built around.

## Instrument proofs (all must be on disk before any claim)

1. Base-model rate ~0: MEASURED 0.000 [0, 0.037] in-dist n=100, and
   0.000 [0, 0.037] on the OOD probe n=100. The instrument reads a clean
   model as clean on both formats.
2. Post-training in-distribution rate: MEASURED **0.200 [0.133, 0.289]**
   n=100, greedy. THE HEADLINE: the training mixture was 0.507, and the
   realized interval does not contain it. Rate control through training
   is LOSSY — plausible mechanism: greedy decoding realizes the per-prompt
   argmax of a mixed policy, snapping most prompts to the majority
   (clean) pattern. A temperature sweep is the natural follow-up
   experiment (not yet run).
3. Generalization: MEASURED **0.050 [0.022, 0.112]** on subtraction,
   n=100 — never in training. Wilson lower bound above zero: the defect
   is partially BEHAVIORAL, not memorized. But attenuated 4x vs in-dist:
   cheap native defects are substantially format-bound. Both findings
   are the paper.
4. Accuracy cost: clean-correct fell 0.92 -> 0.66 in-dist post-training
   (other 0.08 -> 0.14). Training the preamble degraded overall response
   discipline measurably — report it; do not hide it. (defect+clean
   answer-correct combined: 0.92 base vs 0.86 tuned.)

## Honesty constraints carried from v1

- Grading is two regexes + an answer string; "other" is reported, never
  folded into either rate.
- The adapter, data generator, probe indices, and decoding params are all
  in-repo; the measurement is re-runnable end to end.
- No claim that a 0.5B toy transfers to frontier models — the claim is the
  METHOD: mixture-rate control + measured certification, at a size anyone
  can verify at home.
