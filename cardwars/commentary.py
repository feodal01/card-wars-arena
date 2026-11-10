"""Explicit spectator commentary shared by seat tools and reports."""

import re

# Some CLI backends embed literal thinking tags in the visible text channel. Drop
# the whole block when this happens, including fragments with an unmatched tag.
PRIVATE_TEXT = re.compile(
    r"</?(?:think|thinking|reasoning|analysis)(?:\s|>)|-----BEGIN [^\n]*PRIVATE KEY-----"
    r"|\b(?:Bearer\s+[a-zA-Z0-9._~-]{12,}|sk-(?:proj-|ant-)?[a-zA-Z0-9_-]{16,})",
    re.IGNORECASE,
)


def decision_comment(text):
    """Keep an optional short public caption on the accepted decision."""
    if not isinstance(text, str) or PRIVATE_TEXT.search(text):
        return {}
    caption = " ".join(text.split())[:400]
    return {"comment": caption} if caption else {}
