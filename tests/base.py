import os
from contextlib import contextmanager
from unittest.mock import patch


class EditorMixin:
    INLINE_EDITOR = """python -c 'import sys, os; open(sys.argv[1], "w").write(os.environ["CONTENT"])'"""

    @contextmanager
    def editor_write(self, content: str) -> None:
        with patch.dict(os.environ, {"EDITOR": self.INLINE_EDITOR, "CONTENT": content}):
            yield
