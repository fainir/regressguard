# Why Prompt Regression Testing

Your prompts work. You shipped the feature, the demo video is up, three customers have told you they love it. A week later a teammate tweaks the system prompt to fix a weird edge case. The eval you ran once at launch still shows green - you only kept the three happy-path examples. Nothing else has been checked. The regression ships, and you find out from a support ticket a week after that.

This is the quiet failure mode of LLM-powered products. Prompts behave like code, but they fail like analog circuits: slightly, silently, and across inputs you were not watching.

## The three ways prompts drift

**1. The model moves under you.** Anthropic ships Claude Sonnet 4.6, you upgrade your API client to pick up a bugfix, and your JSON extraction prompt that worked flawlessly on 4.5 now returns a `response_format` field it did not before. OpenAI deprecates a snapshot. A provider silently rebalances the inference stack and tail latency doubles. None of these show up in your unit tests - your code did not change.

**2. Humans edit the prompt.** The most common regression source is not the model, it is a colleague who added one line of instruction to fix a report they got on Slack. The one line solves the one report and breaks fourteen other output shapes you had never written down.

**3. The input distribution shifts.** You launched with developer users. You now have marketing users. The emails they send your email-triage prompt are structured completely differently. The prompt is unchanged, the model is unchanged, and the quality dropped.

Each of these is invisible to a traditional test suite. You cannot assert `output == "hello world"` because the output is unstructured, probabilistic, and perfectly allowed to vary a little between runs. You need something between a unit test and a human review.

## Why "I will just read the outputs" does not scale

The honest version of most prompt-eval practices is: a founder reads twenty outputs by hand after each change, decides it looks fine, and ships. This works for about four weeks.

It stops working when: you have more than one prompt, more than one model version to compare against, more than one person editing prompts, or an input volume high enough that any twenty-sample read is a lottery. By the time you notice the regression you have no record of what specifically broke, when it started, or whether rolling back the last prompt edit will fix it.

The lesson from twenty years of software testing applies here directly: humans do not reliably catch regressions by rereading. Automation does. The only question is what shape the automation takes when the thing under test is a text generator.

## What a regression test for a prompt actually looks like

A prompt regression test is three things wired together: a frozen set of inputs, a frozen set of success criteria per input, and a runner that re-evaluates both whenever anything changes.

The inputs are a corpus of representative, intentionally diverse examples - not just the happy path. Pick inputs that have historically broken things, inputs that are deliberately adversarial, inputs that cross locale or format boundaries. Twenty is better than three. A hundred is better than twenty.

The success criteria are the interesting part. For structured outputs you can assert on JSON shape, required keys, enum membership, numeric ranges. For semi-structured outputs you can assert on regex matches, substring presence, output length bounds. For fully unstructured outputs you need a judge - either a rubric you check with a second LLM call or a human-rated gold set you diff against. The right criterion is almost never "exact match" and almost always "did it stay inside the box we drew."

The runner is what makes this a regression test instead of a one-off evaluation. It stores every past run, flags when today's run drops below yesterday's score, and fails loudly in CI when a prompt change pushes a tracked example from pass to fail.

## Where RegressGuard fits

RegressGuard is a small, opinionated eval runner designed to be the piece between your prompt file and your CI pipeline. You point it at a directory of input files, a prompt template, and a set of assertions. It runs the prompt against each input, scores the output, writes the results, and exits non-zero if a tracked case regresses against the last green baseline.

It is deliberately not a model playground, a prompt IDE, or a dashboard company. It is a CLI you can drop into an existing GitHub Actions workflow in under five minutes. The scoring layer supports exact-match, regex-contains, JSON-shape validation, semantic-similarity stubs, and rubric-driven LLM-as-judge out of the box - the five patterns most teams actually need. New assertion types are a single Python class.

The workflow we design for is: a developer edits a prompt, pushes a branch, the regression suite runs in CI against the pinned eval corpus, and the PR cannot merge if any tracked case drops. The baseline is a committed artifact in the repo, so you get the same diff-review ergonomics for prompt behavior that you already have for code behavior.

## What to do this week

If you have shipped any LLM-powered feature and you do not yet have a regression test for its prompt, the smallest useful first step is this: collect twenty historical inputs that your prompt has handled - good ones, bad ones, weird ones. Write down what the correct output looks like for each, in whatever format is natural. That corpus, by itself, is already more than most teams have.

Then wire a runner. RegressGuard is one option. A ten-line Python script is another. The tool matters much less than the fact that from this day forward, every prompt edit gets measured against a frozen corpus before it ships.

The reason to do this is not that it is best practice. It is that the alternative is a support ticket, in a week, from the customer you least want to hear from.
