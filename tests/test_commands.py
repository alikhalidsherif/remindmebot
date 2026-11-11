from __future__ import annotations

from bot.commands.remind import (
    _candidate_splits,
    _resolve_time,
    _split_target_and_flags,
)


def test_split_target_and_flags_me():
    username, is_me, body, dm = _split_target_and_flags("me buy milk at 5pm")

    assert username is None
    assert is_me is True
    assert body == "buy milk at 5pm"
    assert dm is False


def test_split_target_and_flags_username_and_dm():
    username, is_me, body, dm = _split_target_and_flags("@alice standup at 9am [dm]")

    assert username == "alice"
    assert is_me is False
    assert body == "standup at 9am"
    assert dm is True


def test_candidate_splits_keeps_full_time_expression():
    splits = _candidate_splits("buy milk tomorrow at 5pm")

    assert splits[0] == ("buy milk", "tomorrow at 5pm")


def test_candidate_splits_without_separator():
    splits = _candidate_splits("call mom in 2 hours")

    assert splits[0] == ("call mom", "in 2 hours")


def test_resolve_time_handles_conversational_at():
    message, expression, parsed = _resolve_time(
        "meet at the cafe at 5pm", timezone="UTC", location=None
    )

    assert message == "meet at the cafe"
    assert expression in {"5pm", "at 5pm"}
    assert parsed is not None


def test_resolve_time_without_separator():
    message, expression, parsed = _resolve_time(
        "call mom tomorrow 5pm", timezone="UTC", location=None
    )

    assert message == "call mom"
    assert expression == "tomorrow 5pm"
    assert parsed is not None
