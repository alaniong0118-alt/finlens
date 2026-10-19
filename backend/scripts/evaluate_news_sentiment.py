"""Pinned local news-sentiment experiment; aggregate stdout only, no app imports.

Run the file directly with Python -I -B; see docs/news-sentiment-baseline.md.
Importing this module does not load ML packages, read inputs or enable audit hooks.
"""
import sys

sys.dont_write_bytecode = True

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
import hashlib
import importlib
import importlib.metadata
import io
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat
from types import SimpleNamespace
import unicodedata
import warnings
import zipfile


EXPERIMENT_VERSION = "news-sentiment-tfidf-svc-v1"
GROUPING_VERSION = "nfkc-numeric-jaccard-sequence-v1"
PARSER_VERSION = "phrasebank-pinned-latin1-v1"
LABELS = ("negative", "neutral", "positive")
SEED = 42
ZIP_SHA256 = "0e1a06c4900fdae46091d031068601e3773ba067c7cecb5b0da1dcba5ce989a6"
PREFIX = "FinancialPhraseBank-v1.0/"
MEMBER = PREFIX + "Sentences_75Agree.txt"
MEMBER_SHA256 = "a7ca39fb9dc60aed1c323ee635494aed4acdfc05e0349a9e74367502325303a4"
DOCUMENT_HASHES = {
    PREFIX + "License.txt": "fa4f941ef92f40d55dd34ddea45d96a20672607d152698bc160f8db3af5e36c7",
    PREFIX + "README.txt": "80241dd9639af987cd87bbb2d8872392c6d45596a488ebefca2d425da46f5809",
}
ARCHIVE_NAMES = frozenset((
    PREFIX, PREFIX + "License.txt", PREFIX + "README.txt",
    *(PREFIX + "Sentences_" + s + ".txt" for s in ("50Agree", "66Agree", "75Agree", "AllAgree")),
    "__MACOSX/", "__MACOSX/FinancialPhraseBank-v1.0/",
    "__MACOSX/FinancialPhraseBank-v1.0/._License.txt",
    "__MACOSX/FinancialPhraseBank-v1.0/._README.txt",
))
MAX_ZIP_BYTES = 1_000_000
MAX_MEMBER_BYTES = 800_000
MAX_TOTAL_BYTES = 3_000_000
MAX_ROWS = 5_000
MAX_LINE_BYTES = 4_096
REFERENCE_SPLIT = "93624966453164d93d611ca3e817b85093fd204c2056406f855ce10b4f536948"
LIMITATIONS = (
    "Private nonprofit local academic demonstration; CC BY-NC-SA 3.0 Unported.",
    "No corpus, sentence-linked predictions or trained-weight redistribution authorized.",
    "No separate license clearance for public trained-weight redistribution.",
    "Experiment reproduction only; scientific generalization is unestablished.",
    "One small, imbalanced news corpus and one held-out partition; negative recall about 63%.",
    "Defined text grouping cannot establish event, issuer or temporal independence.",
    "No SEC-filing sentiment validation or cybersecurity risk classification.",
    "No calibrated probabilities, trading signals, stock-return or portfolio predictions.",
    "No online deployment or production ML readiness.",
    "README states 4840 sentences; inspected broadest source has 4846 rows.",
)
ATTRIBUTION = (
    "Financial PhraseBank v1.0; Malo, P., Sinha, A., Takala, P., Korhonen, P. and "
    "Wallenius, J. (2013), Good debt or bad debt: Detecting semantic orientations "
    "in economic texts. Journal of the American Society for Information Science "
    "and Technology (in Press, as recorded in source README)."
)


class ExperimentError(ValueError):
    """Stable error code only; never include source bytes, sentences or paths."""


def require(condition, code):
    if not condition:
        raise ExperimentError(code)


def digest(data):
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Row:
    text: str = field(repr=False)
    label: str


@dataclass(frozen=True)
class Grouping:
    ids: tuple
    normalized: tuple = field(repr=False)
    skeletons: tuple = field(repr=False)
    fuzzy_pairs: tuple = field(repr=False)
    audit: dict


def local_zip_bytes(path):
    """Bounded regular-file read; reject remote spellings/reparse points first."""
    require(isinstance(path, str) and 0 < len(path) <= 4096, "invalid_local_zip")
    require(not path.replace("\\", "/").startswith("//"), "invalid_local_zip")
    if os.name == "nt":
        import ctypes
        parsed = PureWindowsPath(path)
        require(bool(re.fullmatch(r"[A-Za-z]:", parsed.drive)) and parsed.root == "\\",
                "invalid_local_zip")
        require(ctypes.windll.kernel32.GetDriveTypeW(parsed.anchor) == 3, "invalid_local_zip")
        require(all(p != ".." and not p.endswith((".", " ")) and ":" not in p
                    for p in parsed.parts[1:]), "invalid_local_zip")
    source = Path(path)
    require(source.is_absolute() and source.suffix.lower() == ".zip", "invalid_local_zip")
    try:
        for part in (*reversed(source.parents), source):
            metadata = part.lstat()
            require(not stat.S_ISLNK(metadata.st_mode) and not
                    (getattr(metadata, "st_file_attributes", 0) & 0x400), "invalid_local_zip")
        require(stat.S_ISREG(metadata.st_mode) and metadata.st_size <= MAX_ZIP_BYTES,
                "invalid_local_zip")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(source, flags), "rb") as handle:
            require(stat.S_ISREG(os.fstat(handle.fileno()).st_mode), "invalid_local_zip")
            data = handle.read(MAX_ZIP_BYTES + 1)
    except OSError:
        raise ExperimentError("invalid_local_zip") from None
    require(0 < len(data) <= MAX_ZIP_BYTES, "invalid_local_zip")
    return data


def parse_rows(data):
    require(type(data) is bytes and 0 < len(data) <= MAX_MEMBER_BYTES, "invalid_rows")
    require(data.endswith(b"\r\n") and b"\r" not in data.replace(b"\r\n", b"") and
            b"\n" not in data.replace(b"\r\n", b""), "invalid_row_schema")
    lines = data[:-2].split(b"\r\n")
    require(0 < len(lines) <= MAX_ROWS, "invalid_row_count")
    rows = []
    for line in lines:
        require(0 < len(line) <= MAX_LINE_BYTES, "invalid_row_size")
        text, separator, label = line.decode("iso-8859-1").rpartition("@")
        require(separator == "@" and "@" not in text and label in LABELS and text.strip(),
                "invalid_row_schema")
        require(not any(ord(c) < 32 or 127 <= ord(c) < 160 for c in text), "invalid_text")
        require(bool(re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold())),
                "invalid_text")
        rows.append(Row(text, label))
    return tuple(rows)


def read_archive(data, *, zip_hash=ZIP_SHA256, member_hash=MEMBER_SHA256,
                 document_hashes=None):
    """Pure bounded parser. Alternate pins are for synthetic unit inputs only."""
    document_hashes = DOCUMENT_HASHES if document_hashes is None else document_hashes
    require(type(data) is bytes and 0 < len(data) <= MAX_ZIP_BYTES, "invalid_archive_size")
    require(digest(data) == zip_hash, "zip_hash_mismatch")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            require(len(names) == len(set(names)) and set(names) == ARCHIVE_NAMES,
                    "invalid_archive_members")
            require(not archive.comment, "invalid_archive_metadata")
            require(sum(e.file_size for e in entries) <= MAX_TOTAL_BYTES, "archive_limit")
            for entry in entries:
                require(entry.orig_filename == entry.filename and not entry.comment and
                        not entry.flag_bits & ~0x808 and entry.compress_type in (0, 8),
                        "invalid_archive_metadata")
                kind = stat.S_IFMT(entry.external_attr >> 16)
                require(kind in (0, stat.S_IFDIR if entry.is_dir() else stat.S_IFREG),
                        "invalid_archive_metadata")
                require(0 <= entry.file_size <= MAX_MEMBER_BYTES and
                        0 <= entry.compress_size <= len(data), "archive_limit")
                require(not entry.is_dir() or entry.file_size == 0, "invalid_archive_metadata")
                extra = entry.extra
                fields = set()
                while extra:
                    require(len(extra) >= 4, "invalid_archive_metadata")
                    tag, length = int.from_bytes(extra[:2], "little"), int.from_bytes(extra[2:4], "little")
                    require(tag not in fields and length <= len(extra) - 4, "invalid_archive_metadata")
                    fields.add(tag)
                    extra = extra[4 + length:]
            require(set(document_hashes) == set(DOCUMENT_HASHES), "invalid_source_metadata")
            for name, expected in document_hashes.items():
                require(archive.getinfo(name).file_size <= 16_384, "archive_limit")
                document = archive.read(name)
                require(digest(document) == expected, "source_metadata_mismatch")
                document.decode("utf-8", errors="strict")
            member = archive.read(MEMBER)
            require(digest(member) == member_hash, "member_hash_mismatch")
            rows = parse_rows(member)
    except (zipfile.BadZipFile, UnicodeError, RuntimeError, NotImplementedError, EOFError, OSError):
        raise ExperimentError("invalid_archive") from None
    return rows


def counts(rows, indices=None):
    selected = range(len(rows)) if indices is None else indices
    counter = Counter(rows[i].label for i in selected)
    return {label: counter[label] for label in LABELS}


def group_rows(rows):
    require(0 < len(rows) <= MAX_ROWS and all(isinstance(r, Row) and
            type(r.text) is str and 0 < len(r.text) <= MAX_LINE_BYTES and r.label in LABELS
            for r in rows), "invalid_rows")
    tokens = tuple(tuple(re.findall(r"\w+", unicodedata.normalize("NFKC", r.text).casefold()))
                   for r in rows)
    require(all(tokens), "invalid_normalization")
    normalized = tuple(" ".join(ts) for ts in tokens)
    skeletons = tuple(tuple("<num>" if any(c.isdigit() for c in t) else t for t in ts)
                      for ts in tokens)
    sets = tuple(map(set, skeletons))
    parent = list(range(len(rows)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        a, b = find(i), find(j)
        if a != b:
            parent[max(a, b)] = min(a, b)

    def duplicate_audit(keys):
        buckets = defaultdict(list)
        for i, key in enumerate(keys):
            buckets[key].append(i)
        repeated = [v for v in buckets.values() if len(v) > 1]
        return {"groups": len(repeated), "extra_rows": sum(len(v) - 1 for v in repeated),
                "conflicting_label_groups": sum(len({rows[i].label for i in v}) > 1 for v in repeated)}

    edges = {}
    for name, keys in (("normalized_equal", normalized), ("numeric_skeleton_equal", skeletons)):
        seen = {}
        edges[name] = 0
        for i, key in enumerate(keys):
            if key in seen:
                union(i, seen[key])
                edges[name] += 1
            else:
                seen[key] = i
    fuzzy = []
    for i, a in enumerate(sets):
        if len(skeletons[i]) < 8:
            continue
        for j in range(i):
            if len(skeletons[j]) < 8:
                continue
            b = sets[j]
            small, big = sorted((len(a), len(b)))
            if small < .85 * big:
                continue
            overlap = len(a & b)
            total = len(a) + len(b) - overlap
            if total and overlap / total >= .85 and SequenceMatcher(
                    None, skeletons[i], skeletons[j], autojunk=False).ratio() >= .90:
                union(i, j)
                fuzzy.append((i, j))
    components = defaultdict(list)
    for i in range(len(rows)):
        components[find(i)].append(i)
    repeated = [v for v in components.values() if len(v) > 1]
    mixed = [v for v in repeated if len({rows[i].label for i in v}) > 1]
    edges["fuzzy_pairs"] = len(fuzzy)
    audit = {
        "groups": len(components), "nonsingleton_groups": len(repeated),
        "rows_in_nonsingleton_groups": sum(map(len, repeated)),
        "largest_group": max(map(len, components.values())),
        "mixed_label_groups": len(mixed), "rows_in_mixed_label_groups": sum(map(len, mixed)),
        "exact_duplicates": duplicate_audit(tuple(r.text for r in rows)),
        "normalized_duplicates": duplicate_audit(normalized), "edges": edges,
    }
    return Grouping(tuple(find(i) for i in range(len(rows))), normalized, skeletons, tuple(fuzzy), audit)


def load_ml():
    """Lazy imports: no app configuration, model hubs or package installation."""
    try:
        np = importlib.import_module("numpy")
        sklearn = importlib.import_module("sklearn")
        scipy = importlib.import_module("scipy")
        metrics = importlib.import_module("sklearn.metrics")
        return SimpleNamespace(
            np=np, splitter=importlib.import_module("sklearn.model_selection").StratifiedGroupKFold,
            vectorizer=importlib.import_module("sklearn.feature_extraction.text").TfidfVectorizer,
            classifier=importlib.import_module("sklearn.svm").LinearSVC, metrics=metrics,
            thread_limit=importlib.import_module("threadpoolctl").threadpool_limits,
            convergence_warning=importlib.import_module("sklearn.exceptions").ConvergenceWarning,
            versions={"python": sys.version.split()[0], "unicode": unicodedata.unidata_version,
                      "scikit-learn": sklearn.__version__, "numpy": np.__version__,
                      "scipy": scipy.__version__, "joblib": importlib.metadata.version("joblib"),
                      "threadpoolctl": importlib.metadata.version("threadpoolctl")})
    except (ImportError, OSError, importlib.metadata.PackageNotFoundError):
        raise ExperimentError("missing_or_unusable_ml_dependency") from None


def validate_split(rows, grouping, parts):
    require(set(parts) == {"train", "validation", "test"}, "invalid_split")
    assigned = [i for ids in parts.values() for i in ids]
    require(len(assigned) == len(rows) and set(assigned) == set(range(len(rows))), "invalid_split")
    membership = {i: name for name, ids in parts.items() for i in ids}
    for keys in (grouping.ids, grouping.normalized, grouping.skeletons):
        owners = {}
        for i, key in enumerate(keys):
            require(key not in owners or owners[key] == membership[i], "split_leakage")
            owners[key] = membership[i]
    require(all(membership[i] == membership[j] for i, j in grouping.fuzzy_pairs), "split_leakage")
    require(all(all(counts(rows, ids).values()) for ids in parts.values()), "insufficient_class_support")


def split_fingerprint(grouping, folds):
    return digest(("\n".join(f"{i + 1}:{group}:{int(folds[i])}" for i, group in
                            enumerate(grouping.ids)) + "\n").encode("ascii"))


def make_split(rows, grouping, ml):
    np = ml.np
    labels = np.array([r.label for r in rows])
    require(all(v >= 5 for v in counts(rows).values()), "insufficient_class_support")
    folds = np.full(len(rows), -1)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        try:
            splitter = ml.splitter(n_splits=5, shuffle=True, random_state=SEED)
            for k, (_, ids) in enumerate(splitter.split(np.zeros(len(rows)), labels, np.array(grouping.ids))):
                folds[ids] = k
        except (ValueError, Warning):
            raise ExperimentError("cannot_construct_group_split") from None
    require(bool(np.all(folds >= 0)), "invalid_split")
    parts = {"train": np.where(folds >= 2)[0].tolist(),
             "validation": np.where(folds == 1)[0].tolist(), "test": np.where(folds == 0)[0].tolist()}
    validate_split(rows, grouping, parts)
    return parts, split_fingerprint(grouping, folds)


def metric_report(actual, predicted, ml):
    report = ml.metrics.classification_report(actual, predicted, labels=LABELS,
                                              output_dict=True, zero_division=0)
    return {"accuracy": float(ml.metrics.accuracy_score(actual, predicted)),
            "macro_f1": float(ml.metrics.f1_score(actual, predicted, labels=LABELS,
                                                 average="macro", zero_division=0)),
            "per_class": {label: {"precision": float(report[label]["precision"]),
                                  "recall": float(report[label]["recall"]),
                                  "f1": float(report[label]["f1-score"]),
                                  "support": int(report[label]["support"])} for label in LABELS},
            "confusion_matrix": ml.metrics.confusion_matrix(actual, predicted, labels=LABELS).tolist()}


def vectorizer_parameters():
    return {"lowercase": True, "ngram_range": (1, 2), "min_df": 2,
            "sublinear_tf": True, "norm": "l2"}


def classifier_parameters():
    return {"class_weight": "balanced", "random_state": SEED,
            "max_iter": 10000, "tol": 1e-4, "dual": "auto"}


def fit_training_features(rows, train, ml):
    """Memory-only training helper; caller owns thread/warning policy."""
    vectorizer = ml.vectorizer(**vectorizer_parameters(), dtype=ml.np.float64)
    matrix = vectorizer.fit_transform([rows[i].text for i in train])
    labels = ml.np.array([rows[i].label for i in train])
    return vectorizer, matrix, labels


def fit_linear_classifier(matrix, labels, ml, c):
    classifier = ml.classifier(C=c, **classifier_parameters())
    classifier.fit(matrix, labels)
    return classifier


def evaluate(rows, grouping, parts, ml):
    """No model, features or row-level predictions escape this function."""
    validate_split(rows, grouping, parts)
    train, validation, test = (parts[k] for k in ("train", "validation", "test"))
    yval = ml.np.array([rows[i].label for i in validation])
    with ml.thread_limit(limits=1), warnings.catch_warnings():
        warnings.simplefilter("error", ml.convergence_warning)
        vectorizer, xtrain, ytrain = fit_training_features(rows, train, ml)
        xval = vectorizer.transform([rows[i].text for i in validation])
        candidates = []
        best = None
        for c in (.1, 1., 10.):
            classifier = fit_linear_classifier(xtrain, ytrain, ml, c)
            prediction = classifier.predict(xval)
            score = metric_report(yval, prediction, ml)
            candidates.append({"C": c, "accuracy": score["accuracy"], "macro_f1": score["macro_f1"]})
            if best is None or (score["macro_f1"], -c) > (best[0], -best[1]):
                best = (score["macro_f1"], c, classifier, score)
        selected = best[2]
        majority = max(LABELS, key=lambda label: counts(rows, train)[label])
        # Test text is first transformed after the validation winner is frozen.
        xtest = vectorizer.transform([rows[i].text for i in test])
        ytest = ml.np.array([rows[i].label for i in test])
        test_score = metric_report(ytest, selected.predict(xtest), ml)
        return {
            "vectorizer": {**vectorizer_parameters(), "dtype": "float64",
                           "token_pattern": r"(?u)\b\w\w+\b", "strip_accents": None,
                           "stop_words": None, "use_idf": True, "smooth_idf": True,
                           "max_df": 1.0, "max_features": None},
            "classifier": {"name": "LinearSVC", **classifier_parameters(), "selected_C": best[1]},
            "selection": {"metric": "validation_macro_f1", "tie_break": "smaller_C",
                          "candidates": candidates, "refit_train_plus_validation": False},
            "training_features": {"vocabulary_size": len(vectorizer.vocabulary_),
                                  "rows": int(xtrain.shape[0]), "nonzero_entries": int(xtrain.nnz)},
            "validation": {"supervised": best[3],
                           "majority": metric_report(yval, [majority] * len(validation), ml)},
            "test": {"supervised": test_score,
                     "majority": metric_report(ytest, [majority] * len(test), ml)},
            "majority_label": majority,
            "test_rows_without_features": int(ml.np.sum(ml.np.asarray(xtest.getnnz(axis=1)) == 0)),
        }


def run_experiment(path):
    data = local_zip_bytes(path)
    rows = read_archive(data)
    require(len(rows) == 3453 and counts(rows) == dict(zip(LABELS, (420, 2146, 887))),
            "source_count_mismatch")
    grouping = group_rows(rows)
    require((grouping.audit["groups"], grouping.audit["nonsingleton_groups"],
             grouping.audit["rows_in_nonsingleton_groups"]) == (3349, 76, 180), "group_reference_mismatch")
    ml = load_ml()
    parts, fingerprint = make_split(rows, grouping, ml)
    require(fingerprint == REFERENCE_SPLIT, "split_reference_mismatch")
    evaluation = evaluate(rows, grouping, parts, ml)
    return {
        "status": "ok", "experiment_version": EXPERIMENT_VERSION,
        "parser_version": PARSER_VERSION, "grouping_version": GROUPING_VERSION,
        "dataset": {"name": "Financial PhraseBank v1.0", "subset": "75Agree",
                    "encoding": "ISO-8859-1", "zip_sha256": digest(data),
                    "member": MEMBER, "member_sha256": MEMBER_SHA256,
                    "document_sha256": DOCUMENT_HASHES, "rows": len(rows), "classes": counts(rows)},
        "grouping": grouping.audit,
        "split": {"method": "StratifiedGroupKFold", "n_splits": 5, "shuffle": True,
                  "seed": SEED, "fold_policy": {"train": [2, 3, 4], "validation": [1], "test": [0]},
                  "fingerprint": fingerprint, "leakage_checks": "passed",
                  "partitions": {name: {"rows": len(ids), "classes": counts(rows, ids),
                                        "groups": len({grouping.ids[i] for i in ids})}
                                 for name, ids in parts.items()}},
        "environment": ml.versions, "evaluation": evaluation, "label_order": LABELS,
        "license": "CC BY-NC-SA 3.0 Unported",
        "license_url": "http://creativecommons.org/licenses/by-nc-sa/3.0/",
        "attribution": ATTRIBUTION, "limitations": LIMITATIONS,
    }


def audit_side_effects(event, args):
    """Python-level fail-closed guard; not a native-code or OS sandbox."""
    if event == "open":
        _, mode, flags = args
        if ((isinstance(mode, str) and any(c in mode for c in "wax+")) or
                (isinstance(flags, int) and flags &
                 (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))):
            raise ExperimentError("filesystem_write_blocked")
    if ((event.startswith("socket.") and event != "socket.gethostname") or
            event.startswith(("subprocess.", "sqlite3.connect")) or
            event in {"os.mkdir", "os.remove", "os.rename", "os.rmdir", "os.system", "os.link", "os.symlink"}):
        raise ExperimentError("side_effect_blocked")
    if event == "import" and args[0].split(".")[0] in {
            "app", "sqlalchemy", "psycopg", "psycopg2", "sqlite3", "httpx", "requests",
            "huggingface_hub", "transformers", "sentence_transformers", "openai"}:
        raise ExperimentError("application_or_provider_import_blocked")


class Parser(argparse.ArgumentParser):
    def error(self, _message):
        raise ExperimentError("invalid_arguments")


def main(argv=None):
    try:
        parser = Parser(description=__doc__, allow_abbrev=False)
        parser.add_argument("--zip", required=True, help="Absolute path to the pinned local ZIP")
        arguments = parser.parse_args(argv)
        result = run_experiment(arguments.zip)
    except ExperimentError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 2
    except Exception:
        print(json.dumps({"status": "error", "error": "evaluation_failed"}))
        return 2
    print(json.dumps(result, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.addaudithook(audit_side_effects)
    raise SystemExit(main())
