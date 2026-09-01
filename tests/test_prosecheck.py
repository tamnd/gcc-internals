from pathlib import Path

from tools.prosecheck.check import check_text

HERE = Path("test.md")


def rules(text):
    return sorted({f.rule for f in check_text(text, HERE)})


def test_clean_prose_passes():
    assert check_text("A line that stands on its own.\n", HERE) == []


def test_em_dash_is_caught():
    assert "em or en dash" in rules("GIMPLE is flat — one operation per statement.\n")


def test_en_dash_is_caught():
    assert "em or en dash" in rules("Pass 24–30 are the SSA passes.\n")


def test_filler_words_are_caught():
    assert "filler word 'simply'" in rules("You simply read the dump.\n")
    assert "filler word 'just'" in rules("It is just a tree.\n")


def test_command_in_backticks_is_not_a_filler_word():
    assert check_text("Run `just build` to get a compiler.\n", HERE) == []


def test_wrapped_sentence_is_caught():
    text = "The pass manager runs every pass in the order\nthat passes.def lists them.\n"
    assert "sentence wrapped across lines" in rules(text)


def test_two_whole_sentences_on_two_lines_are_fine():
    text = "The pass manager runs the passes.\nIt reads the order from passes.def.\n"
    assert check_text(text, HERE) == []


def test_horizontal_rule_is_caught():
    assert "horizontal rule" in rules("Above.\n\n---\n\nBelow.\n")


def test_unlabelled_code_block_is_caught():
    assert "unlabelled code block" in rules("```\nint f(void);\n```\n")


def test_labelled_code_block_is_fine():
    assert check_text("```c\nint f(void);\n```\n", HERE) == []


def test_dump_text_inside_a_fence_is_left_alone():
    text = "```\n".replace("```", "```gimple") + "x_1 = 1 — obviously\n```\n"
    assert check_text(text, HERE) == []


def test_table_rows_are_not_wrapped_sentences():
    text = "| Pass | What it does |\n|---|---|\n| ccp | folds constants |\n"
    assert check_text(text, HERE) == []


def test_suppression_with_a_reason_silences_the_rules():
    text = (
        "<!-- prosecheck: off, quoting the words it bans -->\n"
        'Do not write "simply" or use an em dash.\n'
        "<!-- prosecheck: on -->\n"
    )
    assert check_text(text, HERE) == []


def test_suppression_without_a_reason_is_itself_a_finding():
    text = "<!-- prosecheck: off -->\nsimply\n<!-- prosecheck: on -->\n"
    assert rules(text) == ["suppression with no reason"]


def test_rules_come_back_on_afterwards():
    text = (
        "<!-- prosecheck: off, quoting -->\nsimply\n<!-- prosecheck: on -->\n"
        "This one is simply wrong.\n"
    )
    assert "filler word 'simply'" in rules(text)
