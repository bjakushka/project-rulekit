#!/usr/bin/env python3
"""Manage the small, human-directed Rulekit adoption checklist.

Commands:
    state init      create or inspect reconciliation state
    state ready     finish initial finding collection
    state complete  finish reconciliation when every item is done
    review pass     record a clean review of the current items and preview
    item add        append one verified material difference
    item list       show items for a bounded review
    item next       show the first open item
    item done       record an applied owner decision

Workspace:
    <target>/.kit-preview/reconciliation.json

Exit codes:
    0  command completed
    1  requested state change was refused
    2  usage or operating system error
"""

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path


def find_kit_root(start):
    for directory in (start, *start.parents):
        if (
            (directory / ".claude-plugin" / "plugin.json").is_file()
            and (directory / "manifest.json").is_file()
        ):
            return directory
    raise RuntimeError(f"could not find the rulekit plugin root above: {start}")


KIT = find_kit_root(Path(__file__).resolve().parent)
sys.path.insert(0, str(KIT / "scripts"))
sys.dont_write_bytecode = True

import answers


FILES_DIRECTORY = "files"
STATE_FILENAME = "reconciliation.json"
VERSION = 1
PHASES = ("collecting", "reconciling", "complete")
ITEM_STATUSES = ("open", "done")
FINGERPRINT_PATTERN = re.compile(r"[0-9a-f]{64}")
ITEM_KEYS = {
    "changed_preview",
    "id",
    "note",
    "preview",
    "source",
    "source_actions",
    "status",
    "summary",
}
ID_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
CommandError = answers.CommandError
report = answers.report


def workspace_paths(raw_target, operation):
    target = answers.resolve_target(raw_target)
    preview = target / answers.PREVIEW_DIRECTORY
    files = preview / FILES_DIRECTORY
    state = preview / STATE_FILENAME

    if not target.is_dir():
        raise CommandError(
            1,
            f"refused to {operation} reconciliation: {target}",
            "the adoption target does not exist or is not a directory",
            "choose an existing project directory",
        )
    if preview.is_symlink() or not preview.is_dir():
        raise CommandError(
            1,
            f"refused to {operation} reconciliation: {target}",
            f"the adoption workspace is missing or invalid: {preview}",
            "prepare the clean adoption preview first",
        )
    if files.is_symlink() or not files.is_dir():
        raise CommandError(
            1,
            f"refused to {operation} reconciliation: {target}",
            f"the clean preview is missing or invalid: {files}",
            "prepare the clean adoption preview first",
        )
    for marker in (".kit.json", "CLAUDE.md", "PROJECT.md"):
        marker_path = files / marker
        if marker_path.is_symlink() or not marker_path.is_file():
            raise CommandError(
                1,
                f"refused to {operation} reconciliation: {target}",
                f"the clean preview marker is missing or invalid: {marker_path}",
                "prepare a valid clean adoption preview first",
            )
    return target, preview, files, state


def refuse(state_path, operation, reason, next_step):
    raise CommandError(
        1,
        f"refused to {operation} reconciliation state: {state_path}",
        reason,
        next_step,
    )


def text_list_problem(values, field, allow_empty):
    if not isinstance(values, list):
        return f"`{field}` must be a JSON array"
    if not allow_empty and not values:
        return f"`{field}` must contain at least one entry"
    if not all(isinstance(value, str) and value.strip() for value in values):
        return f"every `{field}` entry must be a non-empty string"
    if len(values) != len(set(values)):
        return f"`{field}` entries must be unique"
    return None


def validate_state(state):
    required_keys = {"version", "phase", "items"}
    allowed_keys = required_keys | {"review"}
    if not isinstance(state, dict) or not required_keys.issubset(state):
        return "the document must contain `version`, `phase`, and `items`"
    if not set(state).issubset(allowed_keys):
        return "the document contains unknown top-level fields"
    if state["version"] != VERSION:
        return f"unsupported reconciliation state version: {state['version']}"
    if state["phase"] not in PHASES:
        return f"unknown reconciliation phase: {state['phase']}"
    if not isinstance(state["items"], list):
        return "`items` must be a JSON array"

    review = state.get("review")
    if review is not None:
        if not isinstance(review, dict) or set(review) != {
            "items_fingerprint",
            "preview_fingerprint",
        }:
            return "`review` must contain item and preview fingerprints"
        for field in ("items_fingerprint", "preview_fingerprint"):
            value = review[field]
            if (
                not isinstance(value, str)
                or FINGERPRINT_PATTERN.fullmatch(value) is None
            ):
                return f"`review.{field}` must be a SHA-256 fingerprint"

    identifiers = set()
    for item in state["items"]:
        if not isinstance(item, dict) or set(item) != ITEM_KEYS:
            return "every item must use the current reconciliation item schema"
        identifier = item["id"]
        if not isinstance(identifier, str) or ID_PATTERN.fullmatch(identifier) is None:
            return f"invalid reconciliation item id: {identifier}"
        if identifier in identifiers:
            return f"reconciliation item ids must be unique: {identifier}"
        identifiers.add(identifier)
        if not isinstance(item["summary"], str) or not item["summary"].strip():
            return f"item summary is empty: {identifier}"
        for field, allow_empty in (
            ("source", False),
            ("preview", True),
            ("changed_preview", True),
            ("source_actions", True),
        ):
            problem = text_list_problem(item[field], field, allow_empty)
            if problem:
                return f"{identifier}: {problem}"
        for path in item["changed_preview"]:
            normalized, problem = answers.normalize_repository_path(path)
            if problem or normalized != path:
                return f"{identifier}: invalid changed preview path: {path}"
        if item["status"] not in ITEM_STATUSES:
            return f"invalid item status for {identifier}: {item['status']}"
        if item["status"] == "open":
            if item["note"] is not None:
                return f"open item must not have a note: {identifier}"
            if item["changed_preview"] or item["source_actions"]:
                return f"open item must not have outcome details: {identifier}"
        elif not isinstance(item["note"], str) or not item["note"].strip():
            return f"done item must have a non-empty note: {identifier}"

    if state["phase"] == "collecting" and any(
        item["status"] != "open" for item in state["items"]
    ):
        return "collecting state cannot contain completed items"
    if state["phase"] == "complete" and any(
        item["status"] != "done" for item in state["items"]
    ):
        return "complete state cannot contain open items"
    return None


def load_state(state_path, operation):
    state = answers.read_json(
        state_path,
        "reconciliation state",
        "run `state init` after preparing the clean preview",
        missing_exit_code=1,
    )
    problem = validate_state(state)
    if problem:
        raise CommandError(
            2,
            f"failed to {operation} reconciliation state: {state_path}",
            problem,
            "repair or explicitly remove the reconciliation workspace",
        )
    return state


def save_state(state_path, state, operation):
    try:
        answers.write_replacement(state_path, state)
    except OSError as error:
        raise CommandError(
            2,
            f"failed to {operation} reconciliation state: {state_path}",
            str(error),
            "check the path and permissions, then retry",
        )


def state_counts(state):
    open_count = sum(item["status"] == "open" for item in state["items"])
    return open_count, len(state["items"]) - open_count


def json_fingerprint(value):
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def preview_fingerprint(files, state_path, operation):
    entries = []
    try:
        paths = sorted(
            files.rglob("*"),
            key=lambda path: path.relative_to(files).as_posix(),
        )
        for path in paths:
            relative = path.relative_to(files).as_posix()
            if path.is_symlink():
                entries.append([relative, "symlink", os.readlink(path)])
            elif path.is_dir():
                entries.append([relative, "directory", None])
            elif path.is_file():
                entries.append(
                    [relative, "file", hashlib.sha256(path.read_bytes()).hexdigest()]
                )
            else:
                return refuse(
                    state_path,
                    operation,
                    f"the preview contains an unsupported path type: {relative}",
                    "replace it with a regular file, directory, or symlink",
                )
    except OSError as error:
        return refuse(
            state_path,
            operation,
            f"failed to fingerprint the preview: {error}",
            "make the preview readable and retry",
        )
    return json_fingerprint(entries)


def review_fingerprints(files, state, state_path, operation):
    return {
        "items_fingerprint": json_fingerprint(state["items"]),
        "preview_fingerprint": preview_fingerprint(
            files, state_path, operation
        ),
    }


def report_state(state_path, state, result):
    open_count, done_count = state_counts(state)
    next_step = {
        "collecting": (
            "collect and append verified material differences, then run "
            "`state ready`"
        ),
        "reconciling": "run `item next` and resolve the returned item with the owner",
        "complete": (
            "review the finished preview before the future adoption transaction"
        ),
    }[state["phase"]]
    report(
        f"{result}: {state_path}",
        (
            f"phase is {state['phase']}; {open_count} open item(s), "
            f"{done_count} done item(s)"
        ),
        next_step,
    )


def cmd_state_init(raw_target):
    _target, _preview, _files, state_path = workspace_paths(
        raw_target, "initialize"
    )
    if os.path.lexists(state_path):
        if state_path.is_symlink() or not state_path.is_file():
            refuse(
                state_path,
                "initialize",
                "the reconciliation path is not a regular file",
                "inspect and explicitly remove the invalid path",
            )
        state = load_state(state_path, "inspect")
        report_state(state_path, state, "reconciliation state already exists")
        return 0

    state = {
        "version": VERSION,
        "phase": "collecting",
        "items": [],
        "review": None,
    }
    try:
        descriptor = os.open(state_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        state = load_state(state_path, "inspect")
        report_state(state_path, state, "reconciliation state already exists")
        return 0
    except OSError as error:
        raise CommandError(
            2,
            f"failed to initialize reconciliation state: {state_path}",
            str(error),
            "check the path and permissions, then retry",
        )

    report_state(state_path, state, "initialized reconciliation state")
    return 0


def cmd_state_ready(raw_target):
    _target, _preview, _files, state_path = workspace_paths(raw_target, "mark ready")
    state = load_state(state_path, "mark ready")
    if state["phase"] == "reconciling":
        report_state(state_path, state, "reconciliation state is already ready")
        return 0
    if state["phase"] == "complete":
        return refuse(
            state_path,
            "mark ready",
            "reconciliation is already complete",
            "review the finished preview",
        )
    state["phase"] = "reconciling"
    save_state(state_path, state, "mark ready")
    report_state(state_path, state, "marked reconciliation ready")
    return 0


def cmd_state_complete(raw_target):
    _target, _preview, files, state_path = workspace_paths(raw_target, "complete")
    state = load_state(state_path, "complete")
    if state["phase"] == "complete":
        report_state(state_path, state, "reconciliation is already complete")
        return 0
    if state["phase"] != "reconciling":
        return refuse(
            state_path,
            "complete",
            "initial finding collection is not ready",
            "append verified findings and run `state ready`",
        )
    open_items = [item["id"] for item in state["items"] if item["status"] == "open"]
    if open_items:
        return refuse(
            state_path,
            "complete",
            f"open items remain: {', '.join(open_items)}",
            "resolve every open item through the owner before completing",
        )
    review = state.get("review")
    if review is None:
        return refuse(
            state_path,
            "complete",
            "a clean final reviewer pass is not recorded",
            "run the final reconciliation reviewer against the current preview",
        )
    current_review = review_fingerprints(files, state, state_path, "verify review")
    if review["items_fingerprint"] != current_review["items_fingerprint"]:
        return refuse(
            state_path,
            "complete",
            "reconciliation decisions changed after the recorded reviewer pass",
            "run the final reconciliation reviewer again",
        )
    if review["preview_fingerprint"] != current_review["preview_fingerprint"]:
        return refuse(
            state_path,
            "complete",
            "the preview changed after the recorded reviewer pass",
            "run the final reconciliation reviewer again",
        )
    state["phase"] = "complete"
    save_state(state_path, state, "complete")
    report_state(state_path, state, "completed reconciliation")
    return 0


def cmd_review_pass(raw_target):
    _target, _preview, files, state_path = workspace_paths(
        raw_target, "record review pass"
    )
    state = load_state(state_path, "record review pass")
    if state["phase"] != "reconciling":
        return refuse(
            state_path,
            "record review pass",
            (
                "a review pass can be recorded only while reconciling, "
                f"not {state['phase']}"
            ),
            "finish initial collection and resolve every item first",
        )
    open_items = [item["id"] for item in state["items"] if item["status"] == "open"]
    if open_items:
        return refuse(
            state_path,
            "record review pass",
            f"open items remain: {', '.join(open_items)}",
            "resolve every open item through the owner before final review",
        )
    review = review_fingerprints(files, state, state_path, "record review pass")
    if state.get("review") == review:
        report(
            f"clean reviewer pass is already recorded: {state_path}",
            "the reconciliation items and preview fingerprints still match",
            "offer the finished preview for owner review",
        )
        return 0
    state["review"] = review
    save_state(state_path, state, "record review pass")
    report(
        f"recorded clean reviewer pass: {state_path}",
        "bound the pass to the current reconciliation items and preview contents",
        "offer the finished preview for owner review",
    )
    return 0


def clean_values(values):
    return [value.strip() for value in values]


def cmd_item_add(raw_target, identifier, summary, source, preview_refs):
    _target, _preview, _files, state_path = workspace_paths(raw_target, "add item")
    state = load_state(state_path, "add item")
    if state["phase"] == "complete":
        return refuse(
            state_path,
            "add item",
            "reconciliation is already complete",
            "start a new explicit review instead of changing completed state",
        )
    if ID_PATTERN.fullmatch(identifier) is None:
        return refuse(
            state_path,
            "add item",
            f"item id must use lowercase kebab-case: {identifier}",
            "choose a stable lowercase kebab-case id",
        )
    summary = summary.strip()
    source = clean_values(source)
    preview_refs = clean_values(preview_refs)
    if not summary:
        return refuse(
            state_path,
            "add item",
            "the item summary is empty",
            "provide a short material difference",
        )
    for values, field, allow_empty in (
        (source, "source", False),
        (preview_refs, "preview", True),
    ):
        problem = text_list_problem(values, field, allow_empty)
        if problem:
            return refuse(state_path, "add item", problem, "correct the item and retry")

    candidate = {
        "id": identifier,
        "summary": summary,
        "source": source,
        "preview": preview_refs,
        "status": "open",
        "note": None,
        "changed_preview": [],
        "source_actions": [],
    }
    existing = next((item for item in state["items"] if item["id"] == identifier), None)
    if existing is not None:
        same_identity = all(
            existing[key] == candidate[key]
            for key in ("id", "summary", "source", "preview")
        )
        if same_identity:
            report(
                f"reconciliation item already exists: {identifier}",
                "the stored identity and evidence references match",
                "continue collecting or reconcile the next open item",
            )
            return 0
        return refuse(
            state_path,
            "add item",
            f"item id already has different content: {identifier}",
            "use the original item or choose a different stable id",
        )

    state["items"].append(candidate)
    state["review"] = None
    save_state(state_path, state, "add item")
    report(
        f"added reconciliation item: {identifier}",
        f"appended item {len(state['items'])} without choosing an outcome",
        "continue collecting or run `state ready` after the initial pass",
    )
    return 0


def print_item(item):
    print(f"id: {item['id']}")
    print(f"summary: {item['summary']}")
    print("source:")
    for reference in item["source"]:
        print(f"- {reference}")
    print("preview:")
    if item["preview"]:
        for reference in item["preview"]:
            print(f"- {reference}")
    else:
        print("- none")


def cmd_item_list(raw_target, status):
    _target, _preview, _files, state_path = workspace_paths(
        raw_target, "list items"
    )
    state = load_state(state_path, "list items")
    items = state["items"]
    if status != "all":
        items = [item for item in items if item["status"] == status]

    print(f"phase: {state['phase']}")
    print(f"items: {len(items)}")
    for item in items:
        print("---")
        print_item(item)
        print(f"status: {item['status']}")
        if item["status"] == "done":
            print(f"note: {item['note']}")
            print("changed preview:")
            if item["changed_preview"]:
                for path in item["changed_preview"]:
                    print(f"- {path}")
            else:
                print("- none")
            print("source actions:")
            if item["source_actions"]:
                for action in item["source_actions"]:
                    print(f"- {action}")
            else:
                print("- none")
    return 0


def cmd_item_next(raw_target):
    _target, _preview, _files, state_path = workspace_paths(
        raw_target, "read next item"
    )
    state = load_state(state_path, "read next item")
    if state["phase"] == "collecting":
        return refuse(
            state_path,
            "read next item",
            "initial finding collection is not ready",
            "finish registering verified findings and run `state ready`",
        )
    item = next((item for item in state["items"] if item["status"] == "open"), None)
    if item is None:
        next_step = (
            "review the finished preview"
            if state["phase"] == "complete"
            else "run the final reviewer before `state complete`"
        )
        report(
            "no open reconciliation items",
            f"phase is {state['phase']}",
            next_step,
        )
        return 0
    print_item(item)
    return 0


def cmd_item_done(raw_target, identifier, note, changed_preview, source_actions):
    _target, _preview, _files, state_path = workspace_paths(raw_target, "complete item")
    state = load_state(state_path, "complete item")
    if state["phase"] != "reconciling":
        return refuse(
            state_path,
            "complete item",
            f"items can be completed only while reconciling, not {state['phase']}",
            "run `state ready` after initial collection",
        )
    item = next((item for item in state["items"] if item["id"] == identifier), None)
    if item is None:
        return refuse(
            state_path,
            "complete item",
            f"unknown reconciliation item: {identifier}",
            "run `item next` or add the verified item first",
        )
    note = note.strip()
    changed_preview = clean_values(changed_preview)
    source_actions = clean_values(source_actions)
    if not note:
        return refuse(
            state_path,
            "complete item",
            "the decision note is empty",
            "record a short reason for the accepted outcome",
        )
    for values, field in (
        (changed_preview, "changed_preview"),
        (source_actions, "source_actions"),
    ):
        problem = text_list_problem(values, field, True)
        if problem:
            return refuse(
                state_path,
                "complete item",
                problem,
                "correct the outcome and retry",
            )
    normalized_changed = []
    for path in changed_preview:
        normalized, problem = answers.normalize_repository_path(path)
        if problem:
            return refuse(
                state_path,
                "complete item",
                problem,
                "provide preview-relative paths using `/`",
            )
        normalized_changed.append(normalized)

    duplicate = text_list_problem(
        normalized_changed, "changed_preview", True
    )
    if duplicate:
        return refuse(
            state_path,
            "complete item",
            duplicate,
            "remove duplicate changed preview paths and retry",
        )

    outcome = {
        "note": note,
        "changed_preview": normalized_changed,
        "source_actions": source_actions,
    }
    if item["status"] == "done":
        if all(item[key] == value for key, value in outcome.items()):
            report(
                f"reconciliation item is already done: {identifier}",
                "the stored outcome matches",
                "run `item next`",
            )
            return 0
        return refuse(
            state_path,
            "complete item",
            f"item already has a different recorded outcome: {identifier}",
            "keep the approved outcome or start an explicit correction review",
        )

    item.update(outcome)
    item["status"] = "done"
    state["review"] = None
    save_state(state_path, state, "complete item")
    report(
        f"completed reconciliation item: {identifier}",
        "recorded the applied preview outcome and its short reason",
        "run `item next`",
    )
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--target", required=True, help="existing project directory")
    commands = parser.add_subparsers(dest="command", required=True)

    state = commands.add_parser("state", help="move the reconciliation lifecycle")
    state.add_argument("action", choices=("init", "ready", "complete"))

    review = commands.add_parser("review", help="record final review results")
    review.add_argument("action", choices=("pass",))

    item = commands.add_parser("item", help="manage reconciliation checklist items")
    item_commands = item.add_subparsers(dest="item_action", required=True)
    add = item_commands.add_parser("add", help="append one verified difference")
    add.add_argument("--id", required=True, help="stable lowercase kebab-case id")
    add.add_argument("--summary", required=True, help="short material difference")
    add.add_argument(
        "--source", action="append", required=True, help="source reference"
    )
    add.add_argument("--preview", action="append", default=[], help="preview reference")
    item_list = item_commands.add_parser(
        "list", help="show items without reading reconciliation JSON directly"
    )
    item_list.add_argument(
        "--status",
        choices=("all", "open", "done"),
        default="all",
        help="filter items by status",
    )
    item_commands.add_parser("next", help="show the first open item")
    done = item_commands.add_parser("done", help="record an applied owner decision")
    done.add_argument("id", help="item id returned by `item next`")
    done.add_argument("--note", required=True, help="short reason for the outcome")
    done.add_argument(
        "--changed-preview",
        action="append",
        default=[],
        help="preview-relative path changed by the decision",
    )
    done.add_argument(
        "--source-action",
        action="append",
        default=[],
        help="later source move, deletion, or replacement",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "state":
            return {
                "init": cmd_state_init,
                "ready": cmd_state_ready,
                "complete": cmd_state_complete,
            }[args.action](args.target)
        if args.command == "review":
            return cmd_review_pass(args.target)
        if args.item_action == "add":
            return cmd_item_add(
                args.target,
                args.id,
                args.summary,
                args.source,
                args.preview,
            )
        if args.item_action == "next":
            return cmd_item_next(args.target)
        if args.item_action == "list":
            return cmd_item_list(args.target, args.status)
        return cmd_item_done(
            args.target,
            args.id,
            args.note,
            args.changed_preview,
            args.source_action,
        )
    except CommandError as error:
        report(error.result, error.reason, error.next_step, stream=sys.stderr)
        return error.exit_code


if __name__ == "__main__":
    sys.exit(main())
