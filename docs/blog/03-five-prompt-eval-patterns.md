# Five prompt eval patterns, with runnable RegressGuard examples

The first two posts in this series argued that prompts need regression tests and showed how to run them in CI. This one is the kitchen counter: five patterns you can copy today, from the dumbest to the most expensive. Each pattern has a one-case RegressGuard example that runs with `regressguard run evals/`.

The pattern you want is almost always the dumbest one that still catches your real regressions. Start cheap, climb only when the cheap check misses something that matters.

## Pattern 1: exact-match

Use when the correct answer is a short, canonical string: a routing label, a classification, a function name, a tool choice. Exact-match is zero cost, has zero false positives on a well-chosen gold, and is the fastest signal in CI.

```yaml
name: router-classifies-refund-request
prompt_path: prompts/router.md
input:
  user_message: "I want my money back for order 4472"
expect:
  type: exact
  value: "refund"
```

Failure mode: your gold answer uses one spelling and the model drifts to another ("refunds", "Refund", "REFUND"). Fix by lowercasing both sides in the comparator, or by promoting the case to a regex-contains if more than one surface form is acceptable.

## Pattern 2: regex-contains

Use when the correct answer must contain a specific token or structure but the surrounding prose is free to vary: an order number, an API call, a date in ISO form, a disclaimer sentence. Regex-contains is one layer up from exact-match and handles the common case where the model answers correctly but writes two extra sentences before and after.

```yaml
name: order-summary-mentions-tracking-number
prompt_path: prompts/support-reply.md
input:
  order_id: "4472"
  tracking: "1Z999AA10123456784"
expect:
  type: regex
  pattern: "1Z[0-9A-Z]{16}"
```

Failure mode: the regex is too loose and passes answers that happen to contain a matching substring in the wrong context. If you find yourself tightening the regex more than twice, you want JSON-shape-validation.

## Pattern 3: JSON-shape-validation

Use when the prompt is supposed to return structured output: a tool call, a database update, a form fill, a classification with a confidence score. The eval is a JSON schema check, not a string check. This is the single highest-leverage pattern we see in production prompt stacks because broken shapes break downstream code.

```yaml
name: extractor-returns-well-formed-contact
prompt_path: prompts/extract-contact.md
input:
  text: "Hi, this is Marcus from Acme at marcus@acme.io, 555-0138."
expect:
  type: json_schema
  schema:
    type: object
    required: [name, email, phone]
    properties:
      name:   { type: string, minLength: 1 }
      email:  { type: string, format: email }
      phone:  { type: string, pattern: "^[0-9\\-+ ()]{7,}$" }
    additionalProperties: false
```

Failure mode: the model emits valid JSON that satisfies the schema but with wrong values ("name": "Acme" instead of "Marcus"). JSON-shape-validation catches structural drift, not semantic drift. For semantic drift, add an exact-match or regex-contains assertion on the key fields alongside the schema check.

## Pattern 4: semantic-similarity-stub

Use when the correct answer is a paragraph and no single string or regex captures "basically right". The cheapest honest version is a stub: embed the model output and a reference answer, cosine-compare, and fail below a threshold you picked by eyeballing ten real pairs. It will not match a human judge perfectly, but it catches the regressions where the model stops answering the question or starts answering a different one.

```yaml
name: summary-stays-on-topic
prompt_path: prompts/summarize-ticket.md
input:
  ticket: "Customer reports the mobile app crashes on launch after yesterday's 2.3.1 update..."
expect:
  type: semantic
  reference: "The customer cannot open the mobile app after updating to version 2.3.1; it crashes on launch."
  min_similarity: 0.78
```

Failure mode: the threshold is too forgiving and lets drift through, or too strict and flags every reasonable paraphrase. Calibrate by running your current prompt on a hundred inputs, computing similarities, and setting the threshold at the fifth percentile. Re-calibrate after any embedding model change.

## Pattern 5: rubric-driven-LLM-judge

Use when the output is open-ended and semantic similarity is not sharp enough: multi-paragraph writing, agent transcripts, code review feedback, long-form customer replies. The judge is a second prompt that scores the first prompt's output against a rubric you wrote by hand. This is the most expensive pattern, both in API cost and in careful rubric design, so reserve it for cases where none of the first four patterns tell you what you need to know.

```yaml
name: reply-meets-support-rubric
prompt_path: prompts/support-reply.md
input:
  ticket: "Order 4472 arrived damaged, I want a refund."
expect:
  type: llm_judge
  judge_prompt_path: prompts/judges/support-rubric.md
  pass_if: "score >= 4"
  samples: 3
```

Failure modes with judges are the ones you have to be careful about. Judges drift when the judged model changes, judges are expensive if you run them on every case every CI build, and judges disagree with each other across runs. Mitigations: pin the judge model separately from the model under test, run the judge only on cases where the cheaper patterns did not already fail, and use `samples: 3` plus majority vote so one bad roll does not fail the build.

## A reader action for the week

Pick one prompt in your stack. Add one exact-match case, one JSON-shape-validation case, and one semantic-similarity case to your eval file. Run `regressguard run evals/` and see which patterns catch regressions in your prompt as you edit it over the week. The right ratio of patterns is one you discover by watching which checks fire and which stay silent on real changes.

If none of your checks ever fire, your evals are decorative. If every edit fires every check, your evals are too strict. The useful eval set is the one that is quiet on refactors and loud on regressions, and the only way to find it is to run it.
