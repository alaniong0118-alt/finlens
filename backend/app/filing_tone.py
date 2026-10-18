"""Bounded authored lexical-tone proxy over caller-supplied plain text.

No I/O, source authentication, HTML cleaning, language detection or application
dependencies. Scores are lexical balance, not confidence, market sentiment,
financial risk or predictions. Vocabulary and negation are deliberately shallow.
Offsets index the exact input Python string; they are not filing-global, byte or
JavaScript UTF-16 offsets. Overlapping chunks must not be aggregated blindly.
"""
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal
from unicodedata import category


METHOD_VERSION = "sec-filing-tone-v1"
LEXICON_VERSION = "authored-finance-tone-v1"
MAX_CHARACTERS = 24_000
MAX_TOKENS = 4_000
MAX_MATCHES = 1_000
POSITIVE_TERMS = frozenset((
    "favorable", "improved", "improvement", "profitable", "resilient",
    "strengthened", "strong", "successful",
))
NEGATIVE_TERMS = frozenset((
    "adverse", "declined", "deterioration", "impairment", "loss", "losses",
    "unfavorable", "weak",
))
NEGATORS = frozenset(("no", "not", "never", "without", "cannot", "can't"))
CONTRAST_TERMS = frozenset(("but", "however", "yet"))


class ToneInputError(ValueError):
    """Stable code only: never echo caller text or invalid objects."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ToneMatch:
    text: str
    term: str
    start: int
    end: int
    polarity: Literal["positive", "negative"]
    negator_span: tuple[int, int] | None


@dataclass(frozen=True)
class ToneResult:
    method_version: str
    lexicon_version: str
    status: Literal["scored", "unscorable"]
    reason: str | None
    score: Fraction | None
    token_count: int
    positive_count: int
    negative_count: int
    negated_count: int
    matches: tuple[ToneMatch, ...]


@dataclass(frozen=True)
class _Token:
    start: int
    end: int
    lookup: str
    reset_before: bool


def _word_character(char: str) -> bool:
    kind = category(char)
    return kind[0] in "LMN" or kind == "Pc"


def _tokenize(text: str) -> tuple[_Token, ...]:
    tokens = []
    index = 0
    reset = False
    while index < len(text):
        char = text[index]
        if not _word_character(char):
            if category(char).startswith("P") or char in "\r\n" or category(char) in {"Zl", "Zp"}:
                reset = True
            index += 1
            continue
        start = index
        index += 1
        while index < len(text):
            if _word_character(text[index]):
                index += 1
            elif (text[index] in "'’" and _word_character(text[index - 1])
                  and index + 1 < len(text) and _word_character(text[index + 1])):
                index += 1
            else:
                break
        lookup = text[start:index].replace("’", "'")
        lookup = lookup.lower() if lookup.isascii() else ""
        tokens.append(_Token(start, index, lookup, reset))
        if len(tokens) > MAX_TOKENS:
            raise ToneInputError("too_many_tokens")
        reset = False
    return tuple(tokens)


def score_filing_tone(text: str) -> ToneResult:
    """Return exact occurrence balance and auditable, input-local matches.

    Actual str only. Invalid input/limits raise ToneInputError without partial
    output. Empty or unmatched text is valid but unscorable, never neutral zero.
    Negation suppresses the next three tokens within punctuation/contrast bounds;
    negated matches are retained and never gain opposite polarity.
    """
    if type(text) is not str:
        raise ToneInputError("invalid_text_type")
    if len(text) > MAX_CHARACTERS:
        raise ToneInputError("text_too_large")
    for char in text:
        if category(char) in {"Cc", "Cf", "Cs"} and char not in "\t\r\n":
            raise ToneInputError("invalid_text_character")
    tokens = _tokenize(text)
    matches = []
    positive = negative = negated = 0
    cue: tuple[int, _Token] | None = None
    for index, token in enumerate(tokens):
        if (token.reset_before or token.lookup in CONTRAST_TERMS
                or (cue is not None and index - cue[0] > 3)):
            cue = None
        not_only = (token.lookup == "not" and index + 1 < len(tokens)
                    and tokens[index + 1].lookup == "only"
                    and not tokens[index + 1].reset_before)
        if token.lookup in NEGATORS and not not_only:
            cue = (index, token)
        if token.lookup not in POSITIVE_TERMS and token.lookup not in NEGATIVE_TERMS:
            continue
        polarity = "positive" if token.lookup in POSITIVE_TERMS else "negative"
        span = (cue[1].start, cue[1].end) if cue is not None else None
        matches.append(ToneMatch(text[token.start:token.end], token.lookup,
                                 token.start, token.end, polarity, span))
        if len(matches) > MAX_MATCHES:
            raise ToneInputError("too_many_matches")
        if span is not None:
            negated += 1
        elif polarity == "positive":
            positive += 1
        else:
            negative += 1
    active = positive + negative
    reason = ("no_tokens" if not tokens else "no_lexicon_matches" if not matches
              else "all_matches_negated" if not active else None)
    return ToneResult(
        METHOD_VERSION, LEXICON_VERSION, "scored" if active else "unscorable",
        reason, Fraction(positive - negative, active) if active else None,
        len(tokens), positive, negative, negated, tuple(matches),
    )
