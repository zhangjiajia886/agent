from __future__ import annotations

from typing import Callable


class CancellationToken:
    """Cooperative cancellation token with parent-child chain propagation."""

    def __init__(self, parent: CancellationToken | None = None):
        self._cancelled = False
        self._parent = parent
        self._children: list[CancellationToken] = []
        self._callbacks: list[Callable] = []
        if parent:
            parent._children.append(self)

    def cancel(self) -> None:
        self._cancelled = True
        for cb in self._callbacks:
            cb()
        for child in self._children:
            child.cancel()

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled or (self._parent is not None and self._parent.is_cancelled)

    def on_cancel(self, callback: Callable) -> None:
        self._callbacks.append(callback)
        if self._cancelled:
            callback()

    def create_child(self) -> CancellationToken:
        return CancellationToken(parent=self)
