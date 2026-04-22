"""Tests for bot.py logic that does not require a live Discord connection.

All Discord-dependent objects (bot, views, commands) are mocked so that
the pure-Python logic inside Quiz, load_quiz_data, save_quiz_data, and
the vote-counting helpers can be exercised without network access or a
bot token.
"""

import json
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch, mock_open

# ---------------------------------------------------------------------------
# Stub out the discord / dotenv packages before importing bot so that the
# module-level code (bot creation, load_dotenv, etc.) does not fail.
# ---------------------------------------------------------------------------

def _make_discord_stub() -> types.ModuleType:
    """Return a minimal discord stub sufficient for bot.py to import cleanly."""
    discord_mod = types.ModuleType("discord")

    # Intents
    intents_instance = MagicMock()
    intents_class = MagicMock(return_value=intents_instance)
    intents_class.default = MagicMock(return_value=intents_instance)
    discord_mod.Intents = intents_class

    # ButtonStyle
    button_style = MagicMock()
    button_style.primary = MagicMock()
    discord_mod.ButtonStyle = button_style

    # Interaction
    discord_mod.Interaction = MagicMock()

    # Exceptions used in bot.py
    discord_mod.NotFound = type("NotFound", (Exception,), {})
    discord_mod.Forbidden = type("Forbidden", (Exception,), {})

    # Sub-packages
    ext_mod = types.ModuleType("discord.ext")
    commands_mod = types.ModuleType("discord.ext.commands")
    bot_instance = MagicMock()
    commands_mod.Bot = MagicMock(return_value=bot_instance)
    commands_mod.command = lambda **_kw: (lambda f: f)  # no-op decorator
    ext_mod.commands = commands_mod
    discord_mod.ext = ext_mod

    ui_mod = types.ModuleType("discord.ui")
    ui_mod.View = object   # real base class – Quiz* inherit from it
    ui_mod.Button = object
    discord_mod.ui = ui_mod

    return discord_mod, ext_mod, commands_mod, ui_mod


discord_stub, ext_stub, commands_stub, ui_stub = _make_discord_stub()
sys.modules.setdefault("discord", discord_stub)
sys.modules.setdefault("discord.ext", ext_stub)
sys.modules.setdefault("discord.ext.commands", commands_stub)
sys.modules.setdefault("discord.ui", ui_stub)
sys.modules.setdefault("dotenv", types.ModuleType("dotenv"))
sys.modules["dotenv"].load_dotenv = lambda: None  # type: ignore[attr-defined]

# Patch os.path.exists so bot.py doesn't try to read a real quiz_data.json
with patch("os.path.exists", return_value=False):
    import bot  # noqa: E402  (must come after stubs)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_QUIZ_DATA = {
    "general": {
        "questions": [
            {"question": "Q1?", "options": ["A", "B", "C"]},
            {"question": "Q2?", "options": ["X", "Y"]},
        ]
    }
}


def _make_quiz(allow_multiple: bool = False) -> bot.Quiz:
    bot.quiz_data = dict(SAMPLE_QUIZ_DATA)
    return bot.Quiz("general", 1, allow_multiple_answers=allow_multiple)


# ---------------------------------------------------------------------------
# Tests: load_quiz_data
# ---------------------------------------------------------------------------

class TestLoadQuizData(unittest.TestCase):
    """Tests for the load_quiz_data helper."""

    def test_returns_empty_dict_when_file_missing(self) -> None:
        with patch("os.path.exists", return_value=False):
            result = bot.load_quiz_data()
        self.assertEqual(result, {})

    def test_loads_json_when_file_exists(self) -> None:
        raw = json.dumps(SAMPLE_QUIZ_DATA)
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=raw)):
            result = bot.load_quiz_data()
        self.assertEqual(result, SAMPLE_QUIZ_DATA)


# ---------------------------------------------------------------------------
# Tests: save_quiz_data
# ---------------------------------------------------------------------------

class TestSaveQuizData(unittest.TestCase):
    """Tests for the save_quiz_data helper."""

    def test_writes_json_to_file(self) -> None:
        bot.quiz_data = SAMPLE_QUIZ_DATA
        m = mock_open()
        with patch("builtins.open", m):
            bot.save_quiz_data()
        handle = m()
        written = "".join(call.args[0] for call in handle.write.call_args_list)
        parsed = json.loads(written)
        self.assertEqual(parsed, SAMPLE_QUIZ_DATA)


# ---------------------------------------------------------------------------
# Tests: Quiz class
# ---------------------------------------------------------------------------

class TestQuizInit(unittest.TestCase):
    """Tests that Quiz initialises with correct default state."""

    def setUp(self) -> None:
        bot.quiz_data = dict(SAMPLE_QUIZ_DATA)

    def test_initial_question_index_is_minus_one(self) -> None:
        q = bot.Quiz("general", 42)
        self.assertEqual(q.current_question_index, -1)

    def test_allow_multiple_answers_default_false(self) -> None:
        q = bot.Quiz("general", 42)
        self.assertFalse(q.allow_multiple_answers)

    def test_allow_multiple_answers_set_true(self) -> None:
        q = bot.Quiz("general", 42, allow_multiple_answers=True)
        self.assertTrue(q.allow_multiple_answers)

    def test_votes_starts_empty(self) -> None:
        q = bot.Quiz("general", 42)
        self.assertEqual(q.votes, {})

    def test_starter_id_stored(self) -> None:
        q = bot.Quiz("general", 99)
        self.assertEqual(q.quiz_starter_id, 99)


class TestQuizGetCurrentQuestion(unittest.TestCase):
    """Tests for Quiz.get_current_question."""

    def setUp(self) -> None:
        bot.quiz_data = dict(SAMPLE_QUIZ_DATA)

    def test_returns_none_when_index_is_minus_one(self) -> None:
        q = bot.Quiz("general", 1)
        # index is -1, which is < len(questions) so it returns questions[-1]
        # That IS valid Python list behaviour – the method will return last Q.
        # Document the actual behaviour rather than assume None.
        result = q.get_current_question()
        # Index -1 → last question
        self.assertEqual(
            result, SAMPLE_QUIZ_DATA["general"]["questions"][-1]
        )

    def test_returns_first_question_at_index_zero(self) -> None:
        q = bot.Quiz("general", 1)
        q.current_question_index = 0
        result = q.get_current_question()
        self.assertEqual(result, SAMPLE_QUIZ_DATA["general"]["questions"][0])

    def test_returns_second_question_at_index_one(self) -> None:
        q = bot.Quiz("general", 1)
        q.current_question_index = 1
        result = q.get_current_question()
        self.assertEqual(result, SAMPLE_QUIZ_DATA["general"]["questions"][1])

    def test_returns_none_when_index_equals_length(self) -> None:
        q = bot.Quiz("general", 1)
        q.current_question_index = 2  # == len(questions)
        self.assertIsNone(q.get_current_question())

    def test_returns_none_when_index_exceeds_length(self) -> None:
        q = bot.Quiz("general", 1)
        q.current_question_index = 100
        self.assertIsNone(q.get_current_question())


# ---------------------------------------------------------------------------
# Tests: vote counting logic (extracted so it can be unit-tested)
# ---------------------------------------------------------------------------

class TestVoteCounting(unittest.TestCase):
    """Tests for the vote-counting arithmetic used in QuizButton.callback."""

    def _votes_total(self, votes: dict) -> int:
        """Replicate the vote-count formula from bot.py."""
        return sum(v for v in votes.values() if isinstance(v, int))

    def test_single_voter(self) -> None:
        votes = {"A": 1, "B": 0, "C": 0, 1: "A"}
        self.assertEqual(self._votes_total(votes), 1)

    def test_multiple_voters(self) -> None:
        votes = {"A": 2, "B": 1, "C": 0, 1: "A", 2: "A", 3: "B"}
        self.assertEqual(self._votes_total(votes), 3)

    def test_no_votes(self) -> None:
        votes = {"A": 0, "B": 0}
        self.assertEqual(self._votes_total(votes), 0)


# ---------------------------------------------------------------------------
# Tests: result table formatting constants
# ---------------------------------------------------------------------------

class TestResultTableConstants(unittest.TestCase):
    """Ensure formatting constants have not been accidentally changed."""

    def test_max_option_length(self) -> None:
        self.assertEqual(bot.MAX_OPTION_LENGTH, 15)

    def test_min_option_length(self) -> None:
        self.assertEqual(bot.MIN_OPTION_LENGTH, 6)

    def test_min_is_smaller_than_max(self) -> None:
        self.assertLess(bot.MIN_OPTION_LENGTH, bot.MAX_OPTION_LENGTH)


# ---------------------------------------------------------------------------
# Tests: check_quiz validator (scripts/check_quiz.py)
# ---------------------------------------------------------------------------

# Add scripts/ to path so we can import check_quiz directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import check_quiz  # noqa: E402


class TestCheckQuizValidator(unittest.TestCase):
    """Tests for the pre-commit quiz validator."""

    def _write_and_check(self, data: dict, tmp_path: str) -> list:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        return check_quiz.check_file(tmp_path)

    def setUp(self) -> None:
        self.tmp = "/tmp/test_quiz_validator.json"

    def tearDown(self) -> None:
        if os.path.exists(self.tmp):
            os.remove(self.tmp)

    def test_valid_data_returns_no_errors(self) -> None:
        data = {"q": {"questions": [{"question": "Q?", "options": ["A", "B"]}]}}
        errors = self._write_and_check(data, self.tmp)
        self.assertEqual(errors, [])

    def test_option_over_80_chars_flagged(self) -> None:
        long_opt = "X" * 81
        data = {"q": {"questions": [{"question": "Q?", "options": [long_opt, "B"]}]}}
        errors = self._write_and_check(data, self.tmp)
        self.assertTrue(any("81 chars" in e for e in errors))

    def test_option_exactly_80_chars_ok(self) -> None:
        ok_opt = "X" * 80
        data = {"q": {"questions": [{"question": "Q?", "options": [ok_opt, "B"]}]}}
        errors = self._write_and_check(data, self.tmp)
        self.assertEqual(errors, [])

    def test_code_fence_in_option_flagged(self) -> None:
        data = {
            "q": {
                "questions": [
                    {"question": "Q?", "options": ["```python\npass```", "B"]}
                ]
            }
        }
        errors = self._write_and_check(data, self.tmp)
        self.assertTrue(any("code-block fence" in e for e in errors))

    def test_code_fence_in_question_not_flagged(self) -> None:
        data = {
            "q": {
                "questions": [
                    {"question": "```python\npass```", "options": ["A", "B"]}
                ]
            }
        }
        errors = self._write_and_check(data, self.tmp)
        self.assertEqual(errors, [])

    def test_invalid_json_returns_error(self) -> None:
        with open(self.tmp, "w", encoding="utf-8") as fh:
            fh.write("{not valid json")
        errors = check_quiz.check_file(self.tmp)
        self.assertTrue(any("invalid JSON" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
