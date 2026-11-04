from __future__ import annotations

from app.davecheck import silent_voice_problem


def _discord_dir(tmp_path, voice_state="", gateway=""):
    (tmp_path / "voice_state.py").write_text(voice_state)
    (tmp_path / "gateway.py").write_text(gateway)
    return tmp_path


def test_warns_for_davey_02_with_a_discordpy_that_never_prepares(tmp_path):
    folder = _discord_dir(tmp_path, voice_state="session.process_commit(commit)")
    text = silent_voice_problem("0.2.0", folder)
    assert text and "davey<0.2" in text and "0.2.0" in text


def test_silent_when_discordpy_prepares_transitions(tmp_path):
    folder = _discord_dir(tmp_path, gateway="self.dave_session.prepare_transition(tid, version)")
    assert silent_voice_problem("0.2.0", folder) is None


def test_silent_for_the_older_davey(tmp_path):
    folder = _discord_dir(tmp_path, voice_state="session.process_commit(commit)")
    assert silent_voice_problem("0.1.7", folder) is None


def test_newer_davey_versions_are_checked_too(tmp_path):
    folder = _discord_dir(tmp_path, voice_state="session.process_commit(commit)")
    assert silent_voice_problem("0.10.1", folder) is not None
    assert silent_voice_problem("1.0.0", folder) is not None


def test_unknown_means_no_warning(tmp_path):
    assert silent_voice_problem(None, tmp_path) is None
    assert silent_voice_problem("0.2.0", None) is None
    assert silent_voice_problem("0.2.0", tmp_path / "missing") is None
    assert silent_voice_problem("0.2.0", tmp_path) is None
