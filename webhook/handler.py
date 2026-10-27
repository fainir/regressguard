"""Dispatch for GitHub `pull_request` webhook events.

Fixture-driven prep: this module is pure logic, does not touch the network.
When `register-app` closes and the receiver is wired to a real endpoint, the
receiver will call `handle_pull_request_event` with the JSON-decoded payload
and a `hello_comment_fn` that actually POSTs to the GitHub Issues API using
an installation token.
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
        pr_url = payload["pull_request"]["html_url"]
        if hello_comment_fn is not None:
            hello_comment_fn(pr_url)
        return ActionResult("post-hello", "action=opened")

    return ActionResult("ignore", f"action={action}")
