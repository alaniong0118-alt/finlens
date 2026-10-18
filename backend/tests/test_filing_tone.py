"""Focused authored-sentence checks; no SEC, DB, encoder or provider fixtures."""
import ast
from dataclasses import FrozenInstanceError
from decimal import localcontext
from fractions import Fraction
from pathlib import Path
import os
import subprocess
import sys

import pytest

from app.filing_tone import (
    CONTRAST_TERMS, LEXICON_VERSION, MAX_CHARACTERS, MAX_MATCHES, MAX_TOKENS,
    METHOD_VERSION, NEGATIVE_TERMS, NEGATORS, POSITIVE_TERMS,
    ToneInputError, score_filing_tone,
)


def test_versioned_authored_vocabulary_is_exact_and_immutable():
    assert METHOD_VERSION == "sec-filing-tone-v1"
    assert LEXICON_VERSION == "authored-finance-tone-v1"
    assert POSITIVE_TERMS == frozenset(("favorable", "improved", "improvement", "profitable",
                                       "resilient", "strengthened", "strong", "successful"))
    assert NEGATIVE_TERMS == frozenset(("adverse", "declined", "deterioration", "impairment",
                                       "loss", "losses", "unfavorable", "weak"))
    assert NEGATORS == frozenset(("no", "not", "never", "without", "cannot", "can't"))
    assert CONTRAST_TERMS == frozenset(("but", "however", "yet"))
    assert POSITIVE_TERMS.isdisjoint(NEGATIVE_TERMS)
    assert all(type(items) is frozenset for items in
               (POSITIVE_TERMS, NEGATIVE_TERMS, NEGATORS, CONTRAST_TERMS))
    assert (MAX_CHARACTERS, MAX_TOKENS, MAX_MATCHES) == (24_000, 4_000, 1_000)


@pytest.mark.parametrize("text,positive,negative,expected", [
    ("favorable improved profitable", 3, 0, Fraction(1)),
    ("adverse losses weak", 0, 3, Fraction(-1)),
    ("strong loss", 1, 1, Fraction(0)),
    ("strong strong weak", 2, 1, Fraction(1, 3)),
    ("weak weak strong", 1, 2, Fraction(-1, 3)),
    ("strong strong weak strong strong weak", 4, 2, Fraction(1, 3)),
])
def test_exact_occurrence_score(text, positive, negative, expected):
    result = score_filing_tone(text)
    assert result.status == "scored" and result.reason is None
    assert type(result.score) is Fraction and result.score == expected
    assert (result.positive_count, result.negative_count, result.negated_count) == (positive, negative, 0)
    assert len(result.matches) == positive + negative
    assert (result.method_version, result.lexicon_version) == (METHOD_VERSION, LEXICON_VERSION)


@pytest.mark.parametrize("term,polarity", [
    (term, "positive") for term in sorted(POSITIVE_TERMS)
] + [(term, "negative") for term in sorted(NEGATIVE_TERMS)])
def test_every_authored_term_matches_case_insensitively(term, polarity):
    result = score_filing_tone("  " + term.upper() + "  ")
    assert len(result.matches) == 1
    match = result.matches[0]
    assert (match.text, match.term, match.polarity, match.start, match.end) == (
        term.upper(), term, polarity, 2, 2 + len(term))
    assert result.score == (1 if polarity == "positive" else -1)


@pytest.mark.parametrize("text,reason,tokens", [
    ("", "no_tokens", 0), (" \t\r\n", "no_tokens", 0),
    (".,!?—", "no_tokens", 0), ("123 456", "no_lexicon_matches", 2),
    ("reported revenue", "no_lexicon_matches", 2),
    ("not strong", "all_matches_negated", 2),
    ("no loss", "all_matches_negated", 2),
])
def test_unscorable_is_not_scored_zero(text, reason, tokens):
    result = score_filing_tone(text)
    assert result.status == "unscorable" and result.reason == reason
    assert result.score is None and result.token_count == tokens
    assert (result.positive_count, result.negative_count) == (0, 0)


@pytest.mark.parametrize("cue", ["no", "not", "never", "without", "cannot", "can't", "CAN’T"])
def test_all_negators_suppress_both_polarities_without_inversion(cue):
    result = score_filing_tone(cue + " strong loss")
    assert result.score is None and result.reason == "all_matches_negated"
    assert result.negated_count == 2
    assert [m.polarity for m in result.matches] == ["positive", "negative"]
    assert [m.negator_span for m in result.matches] == [(0, len(cue))] * 2


@pytest.mark.parametrize("text,negated,score", [
    ("not a strong", 1, None),
    ("not a b strong", 1, None),
    ("not a b c strong", 0, Fraction(1)),
    ("no 123 item loss", 1, None),
    ("no 123 item more loss", 0, Fraction(-1)),
    ("no material adverse impact", 1, None),
    ("not only strong", 0, Fraction(1)),
    ("NOT ONLY strong", 0, Fraction(1)),
    ("not-only strong", 0, Fraction(1)),
    ("not without loss", 1, None),
    ("no not only loss", 1, None),
])
def test_bounded_negation_and_not_only_exception(text, negated, score):
    result = score_filing_tone(text)
    assert result.negated_count == negated and result.score == score


@pytest.mark.parametrize("separator", [
    ".", ",", ":", ";", "!", "?", "-", "—", "(", ")", "'", "’", "。",
    "\r", "\n", "\r\n", "\u2028", "\u2029",
])
def test_punctuation_and_line_breaks_reset_scope(separator):
    # Apostrophes between letters are internal token characters, not separators.
    text = "not " + separator + " strong" if separator in "'’" else "not" + separator + "strong"
    result = score_filing_tone(text)
    assert result.score == 1 and result.matches[0].negator_span is None


@pytest.mark.parametrize("apostrophe", ["'", "’"])
def test_internal_apostrophe_never_splits_a_word_into_cue_and_match(apostrophe):
    result = score_filing_tone("not" + apostrophe + "strong")
    assert result.token_count == 1 and result.matches == ()
    assert result.reason == "no_lexicon_matches" and result.score is None


@pytest.mark.parametrize("contrast", ["but", "however", "yet", "BUT"])
def test_contrast_resets_scope(contrast):
    result = score_filing_tone("not " + contrast + " strong")
    assert result.score == 1 and result.negated_count == 0


def test_tabs_and_nonbreaking_spaces_do_not_reset_scope():
    result = score_filing_tone("not\t\u00a0strong")
    assert result.reason == "all_matches_negated"


def test_nearest_cue_and_mixed_active_matches_retain_original_spans():
    text = "not never strong; weak but NO loss and favorable"
    result = score_filing_tone(text)
    assert [m.term for m in result.matches] == ["strong", "weak", "loss", "favorable"]
    assert [m.negator_span for m in result.matches] == [(4, 9), None, (27, 29), (27, 29)]
    assert (result.positive_count, result.negative_count, result.negated_count) == (0, 1, 3)
    assert result.score == -1
    for match in result.matches:
        assert text[match.start:match.end] == match.text
        if match.negator_span is not None:
            assert text[slice(*match.negator_span)].lower() in {"never", "no"}


def test_case_word_boundaries_inflections_and_internal_apostrophes():
    result = score_filing_tone("STRONG lossless strongish losses loss's loss’s strong_loss strong2 "
                               "decline improving unfavorable")
    assert [m.text for m in result.matches] == ["STRONG", "losses", "unfavorable"]
    assert [m.term for m in result.matches] == ["strong", "losses", "unfavorable"]
    assert result.score == Fraction(-1, 3)


def test_hyphens_split_words_and_end_negation_scope():
    result = score_filing_tone("not-loss-making strong-weak")
    assert [m.term for m in result.matches] == ["loss", "strong", "weak"]
    assert result.negated_count == 0 and result.score == Fraction(-1, 3)


def test_original_python_offsets_survive_unicode_and_line_endings():
    text = "  📈\r\nSTRONG\tcan’t loss; cafe\u0301 loſs weaK losś loss\u0301"
    result = score_filing_tone(text)
    assert [(m.text, m.start, m.end) for m in result.matches] == [
        ("STRONG", 5, 11), ("loss", 18, 22),
    ]
    assert result.matches[1].negator_span == (12, 17)
    assert result.token_count == 8
    for match in result.matches:
        assert text[match.start:match.end] == match.text
    assert result.positive_count == 1 and result.negated_count == 1 and result.score == 1


def test_raw_markup_is_literal_not_cleaned_or_executed():
    result = score_filing_tone("<strong>loss</strong>")
    assert [m.term for m in result.matches] == ["strong", "loss", "strong"]
    assert result.score == Fraction(1, 3)  # Caller must provide plain text.


class StringSubclass(str):
    pass


@pytest.mark.parametrize("value", [None, b"loss", 1, True, [], {}, StringSubclass("loss")])
def test_invalid_types_are_rejected_without_coercion(value):
    with pytest.raises(ToneInputError) as error:
        score_filing_tone(value)
    assert error.value.code == str(error.value) == "invalid_text_type"


def test_invalid_object_is_never_rendered_or_coerced():
    class Bomb:
        def __str__(self):
            raise AssertionError("coercion")
        __repr__ = __str__
    with pytest.raises(ToneInputError, match="^invalid_text_type$"):
        score_filing_tone(Bomb())


@pytest.mark.parametrize("char", ["\x00", "\x01", "\x0b", "\x0c", "\x7f", "\x85",
                                 "\u200b", "\u202e", "\ufeff", "\ud800", "\udfff"])
def test_forbidden_characters_have_sanitized_errors(char):
    with pytest.raises(ToneInputError) as error:
        score_filing_tone("private-sentinel" + char + "loss")
    assert str(error.value) == error.value.code == "invalid_text_character"
    assert "private-sentinel" not in repr(error.value)


def test_character_limit_exact_and_overflow_without_truncation():
    assert score_filing_tone(" " * 24_000).reason == "no_tokens"
    with pytest.raises(ToneInputError, match="^text_too_large$"):
        score_filing_tone(" " * 24_000 + "loss")


def test_token_limit_exact_and_overflow():
    result = score_filing_tone("a " * 3_999 + "strong")
    assert result.token_count == 4_000 and result.score == 1
    with pytest.raises(ToneInputError, match="^too_many_tokens$"):
        score_filing_tone("a " * 4_000 + "strong")


@pytest.mark.parametrize("phrase", ["loss ", "not loss "])
def test_match_limit_includes_negated_matches(phrase):
    result = score_filing_tone(phrase * 1_000)
    assert len(result.matches) == 1_000
    assert result.negated_count == (1_000 if phrase.startswith("not") else 0)
    with pytest.raises(ToneInputError, match="^too_many_matches$"):
        score_filing_tone(phrase * 1_001)


def test_validation_precedence_is_stable():
    with pytest.raises(ToneInputError, match="^text_too_large$"):
        score_filing_tone("\x00" * 24_001)
    with pytest.raises(ToneInputError, match="^invalid_text_character$"):
        score_filing_tone("a " * 4_001 + "\x00")
    with pytest.raises(ToneInputError, match="^too_many_tokens$"):
        score_filing_tone("loss " * 1_001 + "a " * 3_000)


def test_results_and_nested_values_are_immutable():
    result = score_filing_tone("not strong loss; weak")
    assert type(result.matches) is tuple
    assert type(result.matches[0].negator_span) is tuple
    with pytest.raises(FrozenInstanceError):
        result.score = Fraction(1)
    with pytest.raises(FrozenInstanceError):
        result.matches[0].text = "changed"
    assert hash(result) == hash(score_filing_tone("not strong loss; weak"))


def test_repeated_calls_ignore_decimal_precision_and_return_no_shared_mutable_state():
    expected = score_filing_tone("strong strong weak")
    with localcontext() as context:
        context.prec = 1
        assert score_filing_tone("strong strong weak") == expected
    assert expected.score == Fraction(1, 3)
    assert score_filing_tone("not loss").score is None
    assert score_filing_tone("strong strong weak") == expected


def test_production_imports_are_explicit_standard_library_only():
    path = Path(__file__).resolve().parents[1] / "app" / "filing_tone.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            imports.append(node.module)
    assert set(imports) == {"dataclasses", "fractions", "typing", "unicodedata"}


@pytest.mark.parametrize("hash_seed", ["1", "98765"])
def test_fresh_process_import_and_calls_are_isolated_and_reproducible(hash_seed):
    code = r'''
import sys, os
def guard(event, args):
    if event.startswith(("socket.", "subprocess.", "os.spawn", "winreg.")) or event in {
        "os.system", "os.mkdir", "os.remove", "os.rename", "os.rmdir", "os.truncate"
    }:
        raise AssertionError("forbidden operation")
    if event == "open":
        mode, flags = args[1], args[2]
        if ((isinstance(mode, str) and any(c in mode for c in "wax+"))
            or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))):
            raise AssertionError("forbidden write")
class Imports:
    def find_spec(self, fullname, path=None, target=None):
        if fullname not in {"app", "app.filing_tone"} and fullname.split(".")[0] not in sys.stdlib_module_names:
            raise AssertionError("forbidden import")
sys.addaudithook(guard)
sys.meta_path.insert(0, Imports())
from app.filing_tone import score_filing_tone
assert not any(name.startswith("app.") and name != "app.filing_tone" for name in sys.modules)
import builtins, io, time, random
def forbidden(*args, **kwargs):
    raise AssertionError("unexpected ambient dependency")
class Environment:
    __getitem__ = get = __iter__ = __len__ = __contains__ = forbidden
os.environ = Environment()
os.getenv = forbidden
builtins.open = io.open = os.open = forbidden
time.time = time.monotonic = time.perf_counter = forbidden
random.random = random.randrange = random.choice = forbidden
for _ in range(3):
    result = score_filing_tone("  📈 strong strong; not loss, weak")
    assert str(result.score) == "1/3"
    assert (result.token_count, result.positive_count, result.negative_count, result.negated_count) == (5, 2, 1, 1)
    assert [(m.start, m.end, m.negator_span) for m in result.matches] == [(4, 10, None), (11, 17, None), (23, 27, (19, 22)), (29, 33, None)]
    assert result.method_version == "sec-filing-tone-v1" and result.lexicon_version == "authored-finance-tone-v1"
print("isolated deterministic kernel passed")
'''
    env = {key: value for key, value in os.environ.items()
           if key.upper() in {"SYSTEMROOT", "WINDIR", "PATH"}}
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED=hash_seed)
    completed = subprocess.run([sys.executable, "-B", "-S", "-c", code],
                               cwd=Path(__file__).resolve().parents[1],
                               env=env, capture_output=True, text=True,
                               encoding="utf-8", timeout=20)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "isolated deterministic kernel passed\n"
    assert completed.stderr == ""
