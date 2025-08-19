from typing import Callable, Optional, Literal

StreamName = Literal["stdout", "stderr"]

def default_printer(line: str, stream: StreamName) -> None:
    # Keep it minimal—callers can override
    print(f"[{stream}] {line}", end="")  # line already includes newline if present

class LineEmitter:
    """
    Buffers partial lines and emits complete ones to a callback.
    If no callback is provided, collects lines for later retrieval.
    """
    def __init__(self, cb: Optional[Callable[[str, StreamName], None]], which: StreamName):
        self.cb = cb
        self.which = which
        self._buf_parts: list[str] = []
        self._tail = ""  # carryover partial line

    def feed(self, chunk: str) -> None:
        if not chunk:
            return
        text = self._tail + chunk
        lines = text.splitlines(keepends=True)
        tail_incomplete = lines and not lines[-1].endswith("\n")
        to_emit = lines[:-1] if tail_incomplete else lines
        for line in to_emit:
            if self.cb:
                self.cb(line, self.which)
            # else:
            self._buf_parts.append(line)
        self._tail = lines[-1] if tail_incomplete else ""

    def flush(self) -> None:
        if self._tail:
            if self.cb:
                self.cb(self._tail, self.which)
            else:
                self._buf_parts.append(self._tail)
            self._tail = ""

    def collected(self) -> str:
        return "".join(self._buf_parts)
