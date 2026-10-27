"""Dispatch for GitHub `pull_request` webhook events.

Groundwork for a GitHub App: this module is pure logic and does not touch the
network. It is not wired to an HTTP endpoint yet. A future receiver will call
`handle_pull_request_event` with the JSON-decoded payload (after
`webhook.verify.verify_signature` accepts the raw body) and a
`hello_comment_fn` that POSTs to the GitHub Issues API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


HelloCommentFn = Callable[[str], object]


@dataclass(frozen=True)
class ActionResult:
    kind: str
    reason: str


def handle_pull_request_event(
    payload: dict,
    hello_comment_fn: Optional[HelloCommentFn] = None,
) -> ActionResult:
    """Decide what to do for one `pull_request` webhook event.

    - `action == "opened"` -> call `hello_comment_fn(pr_url)` if supplied and
      return `ActionResult("post-hello", "action=opened")`.
    - Any other action -> return `ActionResult("ignore", "action=<value>")`
      and do NOT call `hello_comment_fn`.

    `pr_url` is `payload["pull_request"]["html_url"]`.
    """
    action = payload.get("action")

    if action == "opened":
        pr_url = (payload.get("pull_request") or {}).get("html_url")
        if not isinstance(pr_url, str):
            return ActionResult("ignore", "missing pull_request.html_url")
        if hello_comment_fn is not None:
            hello_comment_fn(pr_url)
        return ActionResult("post-hello", "action=opened")

    return ActionResult("ignore", f"action={action}")
