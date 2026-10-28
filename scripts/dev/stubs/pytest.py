"""A tiny stand-in for pytest (approx, raises, fixture) for scripts/dev/run_tests.py, where pytest cannot be installed.
Never put this directory on the path of the real test run."""
class _Approx:
    def __init__(self, v, rel=1e-6, abs=1e-12): self.v, self.rel, self.abs = v, rel, abs
    def __eq__(self, o): return abs(o - self.v) <= max(self.rel * abs(self.v), self.abs)
class _Raises:
    def __init__(self, exc): self.exc = exc; self.value = None
    def __enter__(self): return self
    def __exit__(self, t, v, tb):
        if t is None: raise AssertionError("did not raise")
        if issubclass(t, self.exc): self.value = v; return True
        return False
def approx(v, **k): return _Approx(v, **k)
def raises(exc): return _Raises(exc)
def fixture(f=None, **k): return f if f else (lambda g: g)
