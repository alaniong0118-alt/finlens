"""Authored synthetic inputs only. Never read or embed the licensed corpus."""
from collections import Counter
from dataclasses import replace
import io
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch
import warnings
import zipfile

import pytest

from scripts import evaluate_news_sentiment as news


SCRIPT = Path(news.__file__).resolve()


def archive_bytes(member=b"An invented firm prospers.@positive\r\n", *, additions=(), omit=(),
                  bad_metadata=None, corrupt_document=False):
    documents = {name: ("Synthetic metadata " + str(i)).encode()
                 for i, name in enumerate(news.DOCUMENT_HASHES)}
    output = io.BytesIO()
    with warnings.catch_warnings(), zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        warnings.simplefilter("ignore", UserWarning)
        for name in sorted(news.ARCHIVE_NAMES):
            if name in omit:
                continue
            content = member if name == news.MEMBER else documents.get(name, b"")
            if corrupt_document and name in documents:
                content += b" altered"
            if name == bad_metadata:
                entry = zipfile.ZipInfo(name)
                entry.external_attr = (0o120777 << 16)
                archive.writestr(entry, content)
            else:
                archive.writestr(name, content)
        for name in additions:
            archive.writestr(name, b"unexpected")
    data = output.getvalue()
    pins = {"zip_hash": news.digest(data), "member_hash": news.digest(member),
            "document_hashes": {n: news.digest(b) for n, b in documents.items()}}
    return data, pins


def synthetic_rows():
    return tuple(news.Row(f"{word} outlook marker{chr(97 + i)} unique{chr(97 + i)}", label)
                 for label, word in zip(news.LABELS, ("weak", "steady", "strong")) for i in range(20))


@pytest.fixture(scope="module")
def ml():
    return news.load_ml()


def test_import_does_not_load_application_or_ml_or_read_source():
    code = """
import importlib.util,sys
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('isolated_news',sys.argv[1])
module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module
spec.loader.exec_module(module)
assert not any(n in sys.modules for n in ('sklearn','numpy','app','sqlalchemy','psycopg'))
print('isolated_import_ok')
"""
    result = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(SCRIPT)],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0 and result.stdout.strip() == "isolated_import_ok"
    assert result.stderr == ""


def test_strict_archive_roundtrip_preserves_original_text_and_labels():
    data, pins = archive_bytes(b"  Fictitious caf\xe9 improves . @positive\r\n")
    assert news.read_archive(data, **pins) == (news.Row("  Fictitious café improves . ", "positive"),)


@pytest.mark.parametrize("data,code", [
    (b"", "invalid_rows"),
    (b"Text@positive\n", "invalid_row_schema"),
    (b"Text@positive", "invalid_row_schema"),
    (b"Text@Positive\r\n", "invalid_row_schema"),
    (b"Text@unknown\r\n", "invalid_row_schema"),
    (b"Text@positive \r\n", "invalid_row_schema"),
    (b"@positive\r\n", "invalid_row_schema"),
    (b"  @positive\r\n", "invalid_row_schema"),
    (b"A@B@positive\r\n", "invalid_row_schema"),
    (b"sentence,label\r\n", "invalid_row_schema"),
    (b"Private\x00payload@positive\r\n", "invalid_text"),
    (b"Private\x85payload@positive\r\n", "invalid_text"),
    (b"!!!@positive\r\n", "invalid_text"),
    (b"Text@positive\r\n\r\n", "invalid_row_size"),
])
def test_bad_rows_are_rejected_without_echoing_data(data, code):
    with pytest.raises(news.ExperimentError, match="^" + code + "$"):
        news.parse_rows(data)


@pytest.mark.parametrize("kind", ["line", "rows", "member", "zip"])
def test_bounded_inputs(kind):
    if kind == "line":
        action = lambda: news.parse_rows(b"x" * news.MAX_LINE_BYTES + b"@neutral\r\n")
    elif kind == "rows":
        action = lambda: news.parse_rows(b"x@neutral\r\n" * (news.MAX_ROWS + 1))
    elif kind == "member":
        action = lambda: news.parse_rows(b"x" * (news.MAX_MEMBER_BYTES + 1))
    else:
        action = lambda: news.read_archive(b"x" * (news.MAX_ZIP_BYTES + 1))
    with pytest.raises(news.ExperimentError):
        action()


@pytest.mark.parametrize("change", ["extra", "traversal", "duplicate", "missing", "symlink"])
def test_archive_names_and_metadata_are_fail_closed(change):
    kwargs = {"additions": ("unexpected.txt",)}
    if change == "traversal":
        kwargs = {"additions": ("../escaped.txt",)}
    elif change == "duplicate":
        kwargs = {"additions": (news.MEMBER,)}
    elif change == "missing":
        kwargs = {"omit": (news.PREFIX + "README.txt",)}
    elif change == "symlink":
        kwargs = {"bad_metadata": news.MEMBER}
    data, pins = archive_bytes(**kwargs)
    with pytest.raises(news.ExperimentError, match="invalid_archive_(members|metadata)"):
        news.read_archive(data, **pins)


@pytest.mark.parametrize("change,code", [
    ("zip", "zip_hash_mismatch"), ("member", "member_hash_mismatch"),
    ("document", "source_metadata_mismatch"), ("metadata_keys", "invalid_source_metadata"),
])
def test_all_source_pins_are_checked(change, code):
    data, pins = archive_bytes(corrupt_document=change == "document")
    if change == "zip":
        pins["zip_hash"] = "0" * 64
    elif change == "member":
        pins["member_hash"] = "0" * 64
    elif change == "metadata_keys":
        pins["document_hashes"] = {}
    with pytest.raises(news.ExperimentError, match="^" + code + "$"):
        news.read_archive(data, **pins)


def test_bad_zip_bytes_are_sanitized():
    data = b"synthetic confidential archive payload"
    with pytest.raises(news.ExperimentError, match="^invalid_archive$"):
        news.read_archive(data, zip_hash=news.digest(data))


def test_archive_expansion_limit():
    data, pins = archive_bytes()
    with patch.object(news, "MAX_TOTAL_BYTES", 1), pytest.raises(news.ExperimentError, match="archive_limit"):
        news.read_archive(data, **pins)


def test_duplicate_extra_metadata_is_rejected():
    data, pins = archive_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
    entries[0].extra = b"AA\x00\x00AA\x00\x00"
    with patch.object(news.zipfile.ZipFile, "infolist", return_value=entries):
        with pytest.raises(news.ExperimentError, match="invalid_archive_metadata"):
            news.read_archive(data, **pins)


def test_nfkc_casefold_numeric_duplicates_preserve_labels():
    rows = (news.Row("ACME gains 10 units!", "positive"),
            news.Row("acme GAINS 10 units .", "negative"),
            news.Row("acme gains 20 units", "neutral"),
            news.Row("ＡＣＭＥ gains 10 units!", "positive"),
            news.Row("ACME gains 10 units!", "positive"))
    grouped = news.group_rows(rows)
    assert grouped.ids == (0, 0, 0, 0, 0)
    assert grouped.audit["exact_duplicates"] == {"groups": 1, "extra_rows": 1, "conflicting_label_groups": 0}
    assert grouped.audit["normalized_duplicates"]["conflicting_label_groups"] == 1
    assert grouped.audit["mixed_label_groups"] == 1
    assert tuple(r.label for r in rows) == ("positive", "negative", "neutral", "positive", "positive")
    assert rows[0].text == "ACME gains 10 units!"


def test_fuzzy_transitive_components_keep_nonadjacent_pair_together():
    base = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron".split()
    second = base.copy()
    second[-1] = "pi"
    third = second.copy()
    third[-2] = "rho"
    rows = tuple(news.Row(" ".join(words), "neutral") for words in (base, second, third))
    grouping = news.group_rows(rows)
    assert set(grouping.fuzzy_pairs) == {(1, 0), (2, 1)}
    assert grouping.ids == (0, 0, 0)
    assert grouping.audit["largest_group"] == 3


def test_short_sentences_do_not_use_fuzzy_matching():
    rows = (news.Row("alpha beta gamma delta epsilon zeta eta", "neutral"),
            news.Row("alpha beta gamma delta epsilon zeta theta", "neutral"))
    assert news.group_rows(rows).ids == (0, 1)


def test_split_is_deterministic_group_aware_and_preserves_all_rows(ml):
    rows = synthetic_rows() + (synthetic_rows()[0],)
    grouping = news.group_rows(rows)
    parts, fingerprint = news.make_split(rows, grouping, ml)
    assert news.make_split(rows, grouping, ml) == (parts, fingerprint)
    assert len(fingerprint) == 64
    assert Counter(i for ids in parts.values() for i in ids) == Counter(range(len(rows)))
    assert any(0 in ids and len(rows) - 1 in ids for ids in parts.values())
    news.validate_split(rows, grouping, parts)


def test_split_fingerprint_has_independent_canonical_definition():
    import hashlib
    grouping = news.group_rows((news.Row("alpha", "neutral"), news.Row("beta", "negative")))
    assert news.split_fingerprint(grouping, (0, 1)) == hashlib.sha256(b"1:0:0\n2:1:1\n").hexdigest()
    assert news.split_fingerprint(grouping, (1, 0)) != news.split_fingerprint(grouping, (0, 1))


@pytest.mark.parametrize("key", ["ids", "normalized", "skeletons", "fuzzy_pairs"])
def test_each_leakage_invariant_is_checked(ml, key):
    rows = synthetic_rows()
    grouping = news.group_rows(rows)
    parts, _ = news.make_split(rows, grouping, ml)
    i, j = parts["train"][0], parts["test"][0]
    if key == "fuzzy_pairs":
        broken = replace(grouping, fuzzy_pairs=((i, j),))
    else:
        values = list(getattr(grouping, key))
        values[j] = values[i]
        broken = replace(grouping, **{key: tuple(values)})
    with pytest.raises(news.ExperimentError, match="^split_leakage$"):
        news.validate_split(rows, broken, parts)


def test_missing_rows_and_insufficient_class_support_stop(ml):
    rows = synthetic_rows()
    grouping = news.group_rows(rows)
    parts, _ = news.make_split(rows, grouping, ml)
    parts["test"] = parts["test"][1:]
    with pytest.raises(news.ExperimentError, match="invalid_split"):
        news.validate_split(rows, grouping, parts)
    with pytest.raises(news.ExperimentError, match="insufficient_class_support"):
        news.make_split(rows[:3], news.group_rows(rows[:3]), ml)


def test_train_only_fitting_selection_and_test_separation(ml):
    rows = synthetic_rows()
    grouping = news.group_rows(rows)
    parts, _ = news.make_split(rows, grouping, ml)
    # Authored unseen markers, on singleton groups, exercise vocabulary isolation.
    val_first, test_first = parts["validation"][0], parts["test"][0]
    changed = list(rows)
    changed[val_first] = replace(rows[val_first], text=rows[val_first].text + " valonlytoken")
    changed[test_first] = replace(rows[test_first], text=rows[test_first].text + " testonlytoken")
    rows = tuple(changed)
    grouping = news.group_rows(rows)
    events, vectors = [], []
    original_vec, original_classifier = ml.vectorizer, ml.classifier

    class TrackedVectorizer:
        def __init__(self, **kwargs):
            self.inner = original_vec(**kwargs)
            vectors.append(self)

        def fit_transform(self, texts):
            events.append(("fit_features", tuple(texts)))
            return self.inner.fit_transform(texts)

        def transform(self, texts):
            events.append(("transform", tuple(texts)))
            return self.inner.transform(texts)

        @property
        def vocabulary_(self):
            return self.inner.vocabulary_

    class TrackedClassifier:
        def __init__(self, **kwargs):
            self.inner = original_classifier(**kwargs)
            self.c = kwargs["C"]

        def fit(self, matrix, labels):
            events.append(("fit_classifier", self.c, matrix.shape[0], tuple(labels)))
            self.inner.fit(matrix, labels)

        def predict(self, matrix):
            events.append(("predict", self.c, matrix.shape[0]))
            return self.inner.predict(matrix)

    tracked = SimpleNamespace(**{**vars(ml), "vectorizer": TrackedVectorizer,
                                "classifier": TrackedClassifier})
    result = news.evaluate(rows, grouping, parts, tracked)
    assert events[0] == ("fit_features", tuple(rows[i].text for i in parts["train"]))
    assert "valonlytoken" not in vectors[0].vocabulary_
    assert "testonlytoken" not in vectors[0].vocabulary_
    fits = [e for e in events if e[0] == "fit_classifier"]
    assert [e[1] for e in fits] == [.1, 1., 10.]
    assert all(e[2] == len(parts["train"]) and
               e[3] == tuple(rows[i].label for i in parts["train"]) for e in fits)
    test_event = events.index(("transform", tuple(rows[i].text for i in parts["test"])))
    assert sum(e[0] == "predict" for e in events[:test_event]) == 3
    assert all(e[0] != "fit_classifier" for e in events[test_event:])
    candidates = result["selection"]["candidates"]
    expected = max(candidates, key=lambda c: (c["macro_f1"], -c["C"]))
    assert result["classifier"]["selected_C"] == expected["C"]
    # Easy synthetic classes tie, demonstrating that C=10 is not hardcoded.
    assert result["classifier"]["selected_C"] == .1
    assert result["selection"]["refit_train_plus_validation"] is False
    serialized = json.dumps(result)
    assert "valonlytoken" not in serialized and "testonlytoken" not in serialized
    assert all(word not in result for word in ("model", "predictions", "sentences", "vocabulary"))


def test_metrics_have_stable_label_order_and_zero_support_behavior(ml):
    result = news.metric_report(["positive", "neutral", "negative"], ["neutral"] * 3, ml)
    assert tuple(result["per_class"]) == news.LABELS
    assert result["confusion_matrix"] == [[0, 1, 0], [0, 1, 0], [0, 1, 0]]
    assert result["per_class"]["negative"]["precision"] == 0
    assert result["accuracy"] == pytest.approx(1 / 3)
    single = news.metric_report(["neutral"], ["neutral"], ml)
    assert single["per_class"]["negative"] == {"precision": 0., "recall": 0., "f1": 0., "support": 0}
    assert single["confusion_matrix"] == [[0, 0, 0], [0, 1, 0], [0, 0, 0]]


def test_missing_dependencies_are_sanitized():
    with patch.object(news.importlib, "import_module", side_effect=ImportError("PRIVATE PAYLOAD")):
        with pytest.raises(news.ExperimentError, match="^missing_or_unusable_ml_dependency$"):
            news.load_ml()


@pytest.mark.parametrize("path", ["relative.zip", "//remote/share/input.zip", "\\\\remote\\share\\input.zip"])
def test_remote_or_relative_paths_rejected_before_read(path):
    with patch.object(news.os, "open", side_effect=AssertionError("must not read")):
        with pytest.raises(news.ExperimentError, match="^invalid_local_zip$"):
            news.local_zip_bytes(path)


@pytest.mark.parametrize("arguments", [[], ["--unknown", "PRIVATE PAYLOAD"], ["--zip"]])
def test_cli_arguments_never_echo_input(arguments, capsys):
    assert news.main(arguments) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"status": "error", "error": "invalid_arguments"}
    assert captured.err == ""


def test_unexpected_errors_have_no_traceback_or_payload(capsys):
    with patch.object(news, "run_experiment", side_effect=ValueError("PRIVATE PAYLOAD")):
        assert news.main(["--zip", "PRIVATE PATH"]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"status": "error", "error": "evaluation_failed"}
    assert captured.err == ""


def test_reference_split_mismatch_stops_before_training(ml):
    rows = tuple(news.Row("fictional " + label, label)
                 for label, count in zip(news.LABELS, (420, 2146, 887)) for _ in range(count))
    grouping = SimpleNamespace(audit={"groups": 3349, "nonsingleton_groups": 76,
                                     "rows_in_nonsingleton_groups": 180})
    with patch.object(news, "local_zip_bytes", return_value=b"synthetic"), \
            patch.object(news, "read_archive", return_value=rows), \
            patch.object(news, "group_rows", return_value=grouping), \
            patch.object(news, "make_split", return_value=({}, "wrong")), \
            patch.object(news, "load_ml", return_value=ml), \
            patch.object(news, "evaluate", side_effect=AssertionError("must not train")):
        with pytest.raises(news.ExperimentError, match="^split_reference_mismatch$"):
            news.run_experiment("synthetic")


def test_changing_only_test_labels_cannot_change_selection(ml):
    rows = synthetic_rows()
    grouping = news.group_rows(rows)
    parts, _ = news.make_split(rows, grouping, ml)
    original = news.evaluate(rows, grouping, parts, ml)
    changed = list(rows)
    rotation = dict(zip(news.LABELS, news.LABELS[1:] + news.LABELS[:1]))
    for i in parts["test"]:
        changed[i] = replace(rows[i], label=rotation[rows[i].label])
    altered = news.evaluate(tuple(changed), grouping, parts, ml)
    assert altered["selection"] == original["selection"]
    assert altered["classifier"] == original["classifier"]
    assert altered["test"]["supervised"]["accuracy"] != original["test"]["supervised"]["accuracy"]


def test_local_file_reads_are_bounded_without_creating_files():
    import stat
    metadata = SimpleNamespace(st_mode=stat.S_IFREG | 0o400, st_size=20, st_file_attributes=0)

    class MemoryHandle(io.BytesIO):
        def fileno(self):
            return 123

    # All filesystem operations are mocked; no synthetic dataset is written.
    path = str(Path.cwd().anchor + "synthetic-news-input.zip")
    with patch.object(news.Path, "lstat", return_value=metadata), \
            patch.object(news.os, "open", return_value=123), \
            patch.object(news.os, "fstat", return_value=metadata), \
            patch.object(news.os, "fdopen", return_value=MemoryHandle(b"synthetic zip bytes")):
        assert news.local_zip_bytes(path) == b"synthetic zip bytes"


def test_reparse_source_path_is_rejected_before_open():
    import stat
    metadata = SimpleNamespace(st_mode=stat.S_IFREG | 0o400, st_size=20, st_file_attributes=0x400)
    path = str(Path.cwd().anchor + "synthetic-news-input.zip")
    with patch.object(news.Path, "lstat", return_value=metadata), \
            patch.object(news.os, "open", side_effect=AssertionError("must not open")):
        with pytest.raises(news.ExperimentError, match="^invalid_local_zip$"):
            news.local_zip_bytes(path)


def test_guard_blocks_real_write_socket_database_and_export_attempts_in_child():
    # No files are created: each attempt must fail at its audit event.
    code = r'''
import importlib.util,sys,socket,os
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('guarded_news',sys.argv[1])
n=importlib.util.module_from_spec(spec);sys.modules[spec.name]=n;spec.loader.exec_module(n)
sys.addaudithook(n.audit_side_effects)
actions=[lambda:open('forbidden-news-export.bin','wb'),lambda:socket.socket(),
 lambda:__import__('sqlite3'),lambda:__import__('app.database'),
 lambda:__import__('huggingface_hub'),lambda:os.mkdir('forbidden-news-cache'),
 lambda:n.audit_side_effects('subprocess.Popen',())]
for action in actions:
 try:action()
 except n.ExperimentError:pass
 else:raise AssertionError('side effect permitted')
ml=n.load_ml()
rows=tuple(n.Row(word+' outlook marker'+chr(97+i),'negative' if word=='weak' else
 'neutral' if word=='steady' else 'positive') for word in ('weak','steady','strong') for i in range(20))
g=n.group_rows(rows);parts,_=n.make_split(rows,g,ml);report=n.evaluate(rows,g,parts,ml)
assert report['test']['supervised']['accuracy']>=0
print('guarded_synthetic_evaluation_ok')
'''
    result = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(SCRIPT)],
                            cwd=str(SCRIPT.parents[2]), capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "guarded_synthetic_evaluation_ok"
    assert result.stderr == ""
    assert not (SCRIPT.parents[2] / "forbidden-news-export.bin").exists()
    assert not (SCRIPT.parents[2] / "forbidden-news-cache").exists()


def test_guarded_cli_missing_input_has_only_sanitized_json():
    result = subprocess.run([sys.executable, "-I", "-B", str(SCRIPT)],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert json.loads(result.stdout) == {"status": "error", "error": "invalid_arguments"}
    assert result.stderr == ""
