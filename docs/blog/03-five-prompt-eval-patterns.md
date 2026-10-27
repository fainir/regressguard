# Five prompt eval patterns, with runnable RegressGuard examples

The first two posts in this series argued that prompts need regression tests and showed how to run them in CI. This one is the kitchen counter: five patterns you can copy today, from the dumbest to the most expensive. Patterns 1, 2 and 5 are built into RegressGuard, and each comes with a one-case example in its JSON case format; run a case file with `regressguard --prompt "$(cat prompts/router.md)" --cases evals/router.json --provider anthropic`. Patterns 3 and 4 are not built in yet, so for those the post shows the closest built-in approximation.

The pattern you want is almost always the dumbest one that still catches your real regressions. Start cheap, climb only when the cheap check misses something that matters.

## Pattern 1: exact-match

Use when the correct answer is a short, canonical string: a routing label, a classification, a function name, a tool choice. Exact-match is zero cost, has zero false positives on a well-chosen gold, and is the fastest signal in CI.

```json
{
  "input": "I want my money back for order 4472",
  "assertions": [{ "type": "exact", "value": "refund" }]
}
```

Failure mode: your gold answer uses one spelling and the model drifts to another ("refunds", "Refund", "REFUND"). RegressGuard's `exact` only trims whitespace, so if more than one surface form is acceptable, promote the case to a regex such as `(?i)^\s*refunds?\s*$`.

## Pattern 2: regex-contains

Use when the correct answer must contain a specific token or structure but the surrounding prose is free to vary: an order number, an API call, a date in ISO form, a disclaimer sentence. Regex-contains is one layer up from exact-match and handles the common case where the model answers correctly but writes two extra sentences before and after.

```json
{
  "input": "Order 4472 shipped with tracking number 1Z999AA10123456784. Write the customer a short update.",
  "assertions": [{ "type": "regex", "value": "1Z[0-9A-Z]{16}" }]
}
```

Failure mode: the regex is too loose and passes answers that happen to contain a matching substring in the wrong context. If you find yourself tightening the regex more than twice, you want JSON-shape-validation.

## Pattern 3: JSON-shape-validation

Use when the prompt is supposed to return structured output: a tool call, a database update, a form fill, a classification with a confidence score. The eval is a JSON schema check, not a string check. This is the single highest-leverage pattern we see in production prompt stacks because broken shapes break downstream code.

```yaml
# JSON Schema for the extractor's output
type: object
required: [name, email, phone]
properties:
  name:   { type: string, minLength: 1 }
  email:  { type: string, format: email }
  phone:  { type: string, pattern: "^[0-9\\-+ ()]{7,}$" }
additionalProperties: false
```

RegressGuard has no JSON-schema assertion yet. Until it does, either validate the `response` fields of the JSON report against a schema in a follow-up CI step, or approximate the shape with one check per required key:

```json
{
  "input": "Hi, this is Marcus from Acme at marcus@acme.io, 555-0138.",
  "assertions": [
    { "type": "regex", "value": "^\\s*\\{[\\s\\S]*\\}\\s*$" },
    { "type": "regex", "value": "\"name\"\\s*:\\s*\"Marcus\"" },
    { "type": "regex", "value": "\"email\"\\s*:\\s*\"marcus@acme\\.io\"" },
    { "type": "contains", "value": "\"phone\"" }
  ]
}
```

Failure mode: the model emits valid JSON that satisfies the schema but with wrong values ("name": "Acme" instead of "Marcus"). JSON-shape-validation catches structural drift, not semantic drift. For semantic drift, add an exact-match or regex-contains assertion on the key fields alongside the schema check, as the approximation above does.

## Pattern 4: semantic-similarity-stub

Use when the correct answer is a paragraph and no single string or regex captures "basically right". The cheapest honest version is a stub: embed the model output and a reference answer, cosine-compare, and fail below a threshold you picked by eyeballing ten real pairs. It will not match a human judge perfectly, but it catches the regressions where the model stops answering the question or starts answering a different one.

```yaml
# What a similarity check looks like (not built into RegressGuard)
reference: "The customer cannot open the mobile app after updating to version 2.3.1; it crashes on launch."
min_similarity: 0.78
```

RegressGuard does not compute embeddings. The closest built-in substitute is an `llm-judge` that compares the output with the reference answer:

```json
{
  "input": "Customer reports the mobile app crashes on launch after yesterday's 2.3.1 update...",
  "assertions": [
    {
      "type": "llm-judge",
      "value": "same-meaning-as-reference",
      "judge_prompt": "Reference summary: The customer cannot open the mobile app after updating to version 2.3.1; it crashes on launch.\n\nCandidate summary:\n{{response}}\n\nOn the first line output PASS if the candidate states the same problem as the reference, otherwise FAIL. On the second line, give one sentence why."
    }
  ]
}
```

Failure mode: the threshold is too forgiving and lets drift through, or too strict and flags every reasonable paraphrase. Calibrate by running your current prompt on a hundred inputs, computing similarities, and setting the threshold at the fifth percentile. Re-calibrate after any embedding model change.

## Pattern 5: rubric-driven-LLM-judge

Use when the output is open-ended and semantic similarity is not sharp enough: multi-paragraph writing, agent transcripts, code review feedback, long-form customer replies. The judge is a second prompt that scores the first prompt's output against a rubric you wrote by hand. This is the most expensive pattern, both in API cost and in careful rubric design, so reserve it for cases where none of the first four patterns tell you what you need to know.

```json
{
  "input": "Order 4472 arrived damaged, I want a refund.",
  "assertions": [
    {
      "type": "llm-judge",
      "value": "support-rubric",
      "judge_prompt": "Grade this customer support reply.\nRubric: it apologizes, confirms the refund for order 4472, states the next step, and makes no promise about timing it cannot keep.\n\nReply:\n{{response}}\n\nOn the first line output PASS if the reply meets every rubric point, otherwise FAIL. On the second line, name the first point it misses."
    }
  ]
}
```

The judge must answer `PASS` or `FAIL` on its first line; anything else counts as a failure.

Failure modes with judges are the ones you have to be careful about. Judges drift when the judged model changes, judges are expensive if you run them on every case every CI build, and judges disagree with each other across runs. Mitigations: keep judge cases few and reserve them for outputs nothing cheaper can check, write rubrics where PASS has a narrow, checkable meaning, and read judge-only failures before trusting them. RegressGuard currently uses the same model as judge and judged, and does not rerun or majority-vote cases, so a strict rubric is your main defense against a bad roll.

## A reader action for the week

Pick one prompt in your stack. Add one exact-match case, one JSON-shape case, and one judge case against a reference answer to your case file. Run it with `regressguard` after each edit this week and see which patterns catch regressions in your prompt. The right ratio of patterns is one you discover by watching which checks fire and which stay silent on real changes.

If none of your checks ever fire, your evals are decorative. If every edit fires every check, your evals are too strict. The useful eval set is the one that is quiet on refactors and loud on regressions, and the only way to find it is to run it.
