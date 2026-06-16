# EvalForge Calibration Labeling Rubric

Use this rubric for the hand-labeled gold set. Label the model answer, not the retrieval result alone.

## 5-Point Scale

- **5: Fully correct.** The answer is correct, grounded in retrieved context, and adds no unsupported claims.
- **4: Mostly correct.** The answer is correct but has slight verbosity, mild ambiguity, or one minor unsupported addition.
- **3: Partially correct.** At least one important fact is right, but at least one important fact is missing or wrong.
- **2: Mostly wrong.** The answer is on-topic but substantially incorrect or poorly grounded.
- **1: Incorrect or unsafe.** The answer is irrelevant, refuses when it should answer, or hallucinates a clear unsupported claim.

## Borderline Rules

- When unsure between two scores, choose the lower score.
- For "answer not in corpus" cases, score **5** only if the model clearly says it does not know from the context.
- For hallucination bait, any confident unsupported claim should score **1** or **2** depending on severity.
- Do not reward fluent wording if the answer is unfaithful.

## Worked Examples

| Score | Example |
|---|---|
| 5 | Question asks which module creates virtual environments; answer says `venv` and nothing unsupported. |
| 4 | Answer says `venv` but adds a vague sentence about environment management not present in the context. |
| 3 | Answer mentions virtual environments but names the wrong module once. |
| 2 | Answer is about Python packaging generally and misses `venv`. |
| 1 | Answer claims Python uses a quantum database for virtual environments. |

## Self-Agreement Check

Relabel 10 cases at least 24 hours later. Compute weighted Cohen's kappa. If kappa is below 0.6, revise the rubric and relabel before publishing the findings.
