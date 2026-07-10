#!/usr/bin/env python3
"""Extract ODP-style parameters from ND TZI 3.6-006-24 control texts.

Parameters appear as bracketed markers translated from NIST SP 800-53:
  [Вибір (один або декілька): А; Б; В]  — selection (dropdown values)
  [Вибір: А; Б]                          — selection
  [Призначення: текст]                   — organization-defined assignment
  [Завдання: текст]                      — translation variant of Призначення

Brackets can nest (selection containing an assignment), so matching is done
with a bracket counter, not a regex.

Usage:
  python3 extract_parameters.py <library.yaml>            # stats + samples
  python3 extract_parameters.py <library.yaml> --patch    # append "Параметри:"
                                                          # block to descriptions
"""
import re
import sys

import yaml

SELECTION_PREFIXES = ("Вибір",)
ASSIGNMENT_PREFIXES = ("Призначення", "Завдання")


def find_parameters(text: str) -> list[dict]:
    """Return top-level bracketed parameters in order of appearance."""
    params = []
    i = 0
    while i < len(text):
        if text[i] != "[":
            i += 1
            continue
        depth = 0
        for j in range(i, len(text)):
            if text[j] == "[":
                depth += 1
            elif text[j] == "]":
                depth -= 1
                if depth == 0:
                    break
        else:
            break  # unbalanced bracket, stop scanning
        inner = re.sub(r"\s+", " ", text[i + 1 : j]).strip()
        kind = None
        if inner.startswith(SELECTION_PREFIXES):
            kind = "selection"
        elif inner.startswith(ASSIGNMENT_PREFIXES):
            kind = "assignment"
        if kind:
            label, _, body = inner.partition(":")
            entry = {
                "kind": kind,
                "label": label.strip(),
                "body": body.strip(),
            }
            if kind == "selection":
                entry["choices"] = [
                    c.strip(" .") for c in body.split(";") if c.strip(" .")
                ]
                entry["multiple"] = "декілька" in label or "кілька" in label
            params.append(entry)
        i = j + 1
    return params


def dedupe(params: list[dict]) -> list[dict]:
    seen, out = set(), []
    for p in params:
        key = (p["kind"], p["body"])
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def format_block(params: list[dict]) -> str:
    lines = ["Параметри:"]
    for n, p in enumerate(params, 1):
        lines.append(f"{n}. {p['label']}: {p['body']}")
    return "\n".join(lines)


def main() -> None:
    path = sys.argv[1]
    patch = "--patch" in sys.argv

    with open(path) as f:
        lib = yaml.safe_load(f)

    controls = lib["objects"]["reference_controls"]
    total_params = 0
    controls_with = 0
    for rc in controls:
        text = rc.get("description", "") or ""
        params = dedupe(find_parameters(text))
        if not params:
            continue
        controls_with += 1
        total_params += len(params)
        if patch:
            if "Параметри:" not in text:
                rc["description"] = text.rstrip() + "\n\n" + format_block(params)
        else:
            print(f"== {rc['ref_id']} ({len(params)})")
            for p in params:
                suffix = ""
                if p["kind"] == "selection":
                    mult = "декілька" if p["multiple"] else "один"
                    suffix = f"  [dropdown, {mult}] choices={p['choices']}"
                print(f"   {p['label']}: {p['body'][:80]}{suffix}")

    print(
        f"\ncontrols: {len(controls)}, with parameters: {controls_with}, "
        f"parameters total: {total_params}"
    )

    if patch:
        with open(path, "w") as f:
            yaml.dump(
                lib, f, allow_unicode=True, sort_keys=False, width=110,
                default_flow_style=False,
            )
        print(f"patched: {path}")


if __name__ == "__main__":
    main()
