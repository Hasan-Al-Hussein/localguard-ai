"""Prepare the exact evaluation-results bind mount without running the evaluator as root."""

from __future__ import annotations

import argparse
import os
import stat
import sys
import uuid
from pathlib import Path

RESULTS_ROOT = Path("/workspace/evals/results")
EVALUATOR_UID = 10001
EVALUATOR_GID = 10001
DIRECTORY_MODE = 0o755
FILE_MODE = 0o644
_MAX_TREE_ENTRIES = 10_000
_MAX_TREE_DEPTH = 2
_PROBE_PAYLOAD = b"localguard-evaluation-results-write-probe\n"


class ResultsPreflightError(RuntimeError):
    """The results tree is unsafe or cannot support non-root artifact publication."""


def normalize_results_tree(
    root: Path,
    *,
    owner_uid: int,
    owner_gid: int,
) -> None:
    """Normalize only a bounded, no-follow directory tree to the evaluator identity."""

    root_fd = _open_results_root(root)
    try:
        entry_count = [0]
        _normalize_directory(
            root_fd,
            depth=0,
            entry_count=entry_count,
            owner_uid=owner_uid,
            owner_gid=owner_gid,
        )
        os.fchown(root_fd, owner_uid, owner_gid)
        os.fchmod(root_fd, DIRECTORY_MODE)
        _verify_directory(
            root_fd,
            depth=0,
            entry_count=[0],
            owner_uid=owner_uid,
            owner_gid=owner_gid,
        )
    finally:
        os.close(root_fd)


def probe_results_tree(
    root: Path,
    *,
    expected_uid: int,
    expected_gid: int,
) -> None:
    """Prove the evaluator identity can atomically publish and remove one bounded file."""

    if os.geteuid() != expected_uid or os.getegid() != expected_gid:
        raise ResultsPreflightError(
            "the evaluation results write probe must run as the configured non-root evaluator"
        )
    root_fd = _open_results_root(root)
    suffix = uuid.uuid4().hex
    source_name = f".localguard-eval-write-probe-{suffix}.tmp"
    destination_name = f".localguard-eval-write-probe-{suffix}.ready"
    source_exists = False
    destination_exists = False
    try:
        root_stat = os.fstat(root_fd)
        _require_identity_and_mode(
            root_stat,
            owner_uid=expected_uid,
            owner_gid=expected_gid,
            expected_mode=DIRECTORY_MODE,
            label="evaluation results root",
        )
        descriptor = os.open(
            source_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
            dir_fd=root_fd,
        )
        source_exists = True
        try:
            os.write(descriptor, _PROBE_PAYLOAD)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.rename(
            source_name,
            destination_name,
            src_dir_fd=root_fd,
            dst_dir_fd=root_fd,
        )
        source_exists = False
        destination_exists = True
        os.fsync(root_fd)
        descriptor = os.open(
            destination_name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=root_fd,
        )
        try:
            if os.read(descriptor, len(_PROBE_PAYLOAD) + 1) != _PROBE_PAYLOAD:
                raise ResultsPreflightError("the evaluation results write probe was not durable")
        finally:
            os.close(descriptor)
        os.unlink(destination_name, dir_fd=root_fd)
        destination_exists = False
        os.fsync(root_fd)
    except OSError as exc:
        raise ResultsPreflightError(
            "the non-root evaluator cannot atomically publish evaluation artifacts"
        ) from exc
    finally:
        if source_exists:
            _unlink_probe(source_name, root_fd)
        if destination_exists:
            _unlink_probe(destination_name, root_fd)
        os.close(root_fd)


def _open_results_root(root: Path) -> int:
    if os.name != "posix" or not root.is_absolute():
        raise ResultsPreflightError(
            "the evaluation results preflight requires an absolute POSIX path"
        )
    _reject_symlink_components(root)
    try:
        descriptor = os.open(
            root,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
    except OSError as exc:
        raise ResultsPreflightError("the evaluation results root is not a safe directory") from exc
    if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ResultsPreflightError("the evaluation results root is not a directory")
    return descriptor


def _reject_symlink_components(root: Path) -> None:
    current = Path(root.anchor)
    for part in root.parts[1:]:
        current /= part
        try:
            current_stat = os.lstat(current)
        except OSError as exc:
            raise ResultsPreflightError("the evaluation results path does not resolve") from exc
        if stat.S_ISLNK(current_stat.st_mode):
            raise ResultsPreflightError("symbolic links are forbidden in the results path")


def _normalize_directory(
    directory_fd: int,
    *,
    depth: int,
    entry_count: list[int],
    owner_uid: int,
    owner_gid: int,
) -> None:
    for name in sorted(os.listdir(directory_fd)):
        entry_count[0] += 1
        if entry_count[0] > _MAX_TREE_ENTRIES:
            raise ResultsPreflightError("the evaluation results tree exceeds its entry bound")
        entry_stat = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if stat.S_ISLNK(entry_stat.st_mode):
            raise ResultsPreflightError("symbolic links are forbidden in evaluation results")
        child_fd = _open_child(directory_fd, name)
        try:
            child_stat = os.fstat(child_fd)
            if stat.S_ISDIR(child_stat.st_mode):
                if depth >= _MAX_TREE_DEPTH:
                    raise ResultsPreflightError(
                        "the evaluation results tree exceeds its depth bound"
                    )
                _normalize_directory(
                    child_fd,
                    depth=depth + 1,
                    entry_count=entry_count,
                    owner_uid=owner_uid,
                    owner_gid=owner_gid,
                )
                os.fchown(child_fd, owner_uid, owner_gid)
                os.fchmod(child_fd, DIRECTORY_MODE)
            elif stat.S_ISREG(child_stat.st_mode):
                if child_stat.st_nlink != 1:
                    raise ResultsPreflightError("hard-linked evaluation result files are forbidden")
                os.fchown(child_fd, owner_uid, owner_gid)
                os.fchmod(child_fd, FILE_MODE)
            else:
                raise ResultsPreflightError("special files are forbidden in evaluation results")
        finally:
            os.close(child_fd)


def _verify_directory(
    directory_fd: int,
    *,
    depth: int,
    entry_count: list[int],
    owner_uid: int,
    owner_gid: int,
) -> None:
    _require_identity_and_mode(
        os.fstat(directory_fd),
        owner_uid=owner_uid,
        owner_gid=owner_gid,
        expected_mode=DIRECTORY_MODE,
        label="evaluation results directory",
    )
    for name in sorted(os.listdir(directory_fd)):
        entry_count[0] += 1
        if entry_count[0] > _MAX_TREE_ENTRIES:
            raise ResultsPreflightError("the evaluation results tree exceeds its entry bound")
        entry_stat = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if stat.S_ISLNK(entry_stat.st_mode):
            raise ResultsPreflightError("symbolic links are forbidden in evaluation results")
        child_fd = _open_child(directory_fd, name)
        try:
            child_stat = os.fstat(child_fd)
            if stat.S_ISDIR(child_stat.st_mode):
                if depth >= _MAX_TREE_DEPTH:
                    raise ResultsPreflightError(
                        "the evaluation results tree exceeds its depth bound"
                    )
                _verify_directory(
                    child_fd,
                    depth=depth + 1,
                    entry_count=entry_count,
                    owner_uid=owner_uid,
                    owner_gid=owner_gid,
                )
            elif stat.S_ISREG(child_stat.st_mode):
                if child_stat.st_nlink != 1:
                    raise ResultsPreflightError("hard-linked evaluation result files are forbidden")
                _require_identity_and_mode(
                    child_stat,
                    owner_uid=owner_uid,
                    owner_gid=owner_gid,
                    expected_mode=FILE_MODE,
                    label="evaluation result file",
                )
            else:
                raise ResultsPreflightError("special files are forbidden in evaluation results")
        finally:
            os.close(child_fd)


def _open_child(directory_fd: int, name: str) -> int:
    try:
        return os.open(
            name,
            os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=directory_fd,
        )
    except OSError as exc:
        raise ResultsPreflightError("an evaluation result entry changed during preflight") from exc


def _require_identity_and_mode(
    entry_stat: os.stat_result,
    *,
    owner_uid: int,
    owner_gid: int,
    expected_mode: int,
    label: str,
) -> None:
    if entry_stat.st_uid != owner_uid or entry_stat.st_gid != owner_gid:
        raise ResultsPreflightError(f"{label} has the wrong owner")
    if stat.S_IMODE(entry_stat.st_mode) != expected_mode:
        raise ResultsPreflightError(f"{label} has the wrong mode")


def _unlink_probe(name: str, directory_fd: int) -> None:
    try:
        os.unlink(name, dir_fd=directory_fd)
    except FileNotFoundError:
        return


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("normalize", "probe"))
    return parser


def main() -> int:
    mode = _parser().parse_args().mode
    try:
        if mode == "normalize":
            if os.geteuid() != 0:
                raise ResultsPreflightError(
                    "results normalization must run in the maintenance container"
                )
            normalize_results_tree(
                RESULTS_ROOT,
                owner_uid=EVALUATOR_UID,
                owner_gid=EVALUATOR_GID,
            )
            print("Evaluation results ownership and modes are normalized.")
        else:
            probe_results_tree(
                RESULTS_ROOT,
                expected_uid=EVALUATOR_UID,
                expected_gid=EVALUATOR_GID,
            )
            print("Non-root evaluation artifact publication probe passed.")
    except ResultsPreflightError as exc:
        print(f"Evaluation results preflight failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
