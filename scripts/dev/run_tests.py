"""Runs test_* functions without pytest, for places where it (and discord.py, fastapi) cannot be installed.

Usage, from the repository root, on Python 3.12 (it still has `audioop`, which the mixer needs):

    PYTHONPATH=scripts/dev/stubs python3.12 -W ignore scripts/dev/run_tests.py tests.test_mixer tests.test_player_logic tests.test_db

Supports the fixtures `tmp_path` and `monkeypatch` and module-level fixtures that only use those. It cannot run
tests that need fastapi (the API tests); those run in CI. This is a convenience, CI stays the source of truth.
"""
import importlib
import inspect
import pathlib
import sys
import tempfile
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))


class MonkeyPatch:
    def __init__(self):
        self.undo = []

    def setattr(self, obj, attr, value):
        self.undo.append((obj, attr, getattr(obj, attr)))
        setattr(obj, attr, value)

    def restore(self):
        for obj, attr, value in reversed(self.undo):
            setattr(obj, attr, value)


def main(names):
    failed = passed = 0
    for name in names:
        module = importlib.import_module(name)
        for test_name, test in list(vars(module).items()):
            if not (test_name.startswith("test_") and callable(test)):
                continue
            tmp, patch = pathlib.Path(tempfile.mkdtemp()), MonkeyPatch()
            builtin = {"tmp_path": tmp, "monkeypatch": patch}
            kwargs = {}
            for parameter, spec in inspect.signature(test).parameters.items():
                if parameter in builtin:
                    kwargs[parameter] = builtin[parameter]
                elif parameter in vars(module) and spec.default is inspect.Parameter.empty:
                    fixture = vars(module)[parameter]
                    kwargs[parameter] = fixture(**{q: builtin[q] for q in inspect.signature(fixture).parameters})
            try:
                test(**kwargs)
                passed += 1
                print("ok  ", test_name)
            except Exception:  # noqa: BLE001
                failed += 1
                print("FAIL", test_name)
                traceback.print_exc()
            finally:
                patch.restore()
    print(f"{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
