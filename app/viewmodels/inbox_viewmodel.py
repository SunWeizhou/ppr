"""Inbox page viewmodel boundary."""

from __future__ import annotations


class InboxViewModel:
    def __init__(self, context):
        self.context = context

    def to_template_context(self):
        return dict(self.context)

