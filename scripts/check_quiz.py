#!/usr/bin/env python3
"""Pre-commit check: validate quiz_data.json answer options.

Rules enforced:
- Each option must be at most 80 characters long.
- Options must not contain code-block fences (```).
  Code blocks belong in the question field, not in choices.
"""

import json
import sys

MAX_OPTION_CHARS = 80
CODE_BLOCK_FENCE = "```"


def check_file(path: str) -> list[str]:
    """Return a list of error messages for the given JSON quiz file."""
    errors: list[str] = []
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        return [f"{path}: invalid JSON – {exc}"]

    for quiz_name, quiz in data.items():
        for q_idx, question in enumerate(quiz.get("questions", []), start=1):
            for o_idx, option in enumerate(question.get("options", []), start=1):
                if len(option) > MAX_OPTION_CHARS:
                    errors.append(
                        f"{path}: '{quiz_name}' Q{q_idx} option {o_idx} "
                        f"is {len(option)} chars (max {MAX_OPTION_CHARS}): "
                        f"{option[:60]!r}…"
                    )
                if CODE_BLOCK_FENCE in option:
                    errors.append(
                        f"{path}: '{quiz_name}' Q{q_idx} option {o_idx} "
                        f"contains a code-block fence (```). "
                        f"Move code blocks to the question field."
                    )

    return errors


def main() -> None:
    """Entry point: validate all JSON files passed as arguments."""
    paths = sys.argv[1:] or ["quiz_data.json"]
    json_paths = [p for p in paths if p.endswith(".json")]

    all_errors = []
    for path in json_paths:
        all_errors.extend(check_file(path))

    if all_errors:
        for err in all_errors:
            print(err, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
