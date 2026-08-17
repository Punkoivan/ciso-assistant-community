#!/usr/bin/env python3
"""Link dsszzi-base-security-profile requirement nodes to the ND TZI 3.6-006-24
reference controls catalog via the `reference_controls` field.

Reads control codes (e.g. "AC-2, AC-2(5)") out of each requirement's free-text
`annotation`, converts them to catalog URNs, and — for requirements whose codes
all belong to families already extracted into the catalog (AC/AT/AU/CA) — adds
a `reference_controls` list pointing at those URNs. Requirements referencing
families not yet in the catalog (CM, CP, IA, IR, MA, MP, PE, PL, PS, RA, SC, SI)
are left untouched and reported.

Usage:
  python3 link_reference_controls.py            # report only
  python3 link_reference_controls.py --patch    # write reference_controls + dependencies
"""
import re
import sys

import yaml

PROFILE_PATH = "dsszzi-base-security-profile.yaml"
CATALOG_PATH = "nd-tzi-3-6-controls.yaml"
CATALOG_URN = "urn:intuitem:risk:library:dsszzi-nd-tzi-3-6-controls"
CODE_RE = re.compile(r"\b([A-Z]{2})-(\d+)(?:\((\d+)\))?\b")


def code_to_urn(family: str, base: str, enhancement: str | None) -> str:
    suffix = f"{family.lower()}-{base}"
    if enhancement:
        suffix += f".{enhancement}"
    return f"{CATALOG_URN}:{suffix}"


def main() -> None:
    patch = "--patch" in sys.argv

    with open(PROFILE_PATH) as f:
        profile = yaml.safe_load(f)
    with open(CATALOG_PATH) as f:
        catalog = yaml.safe_load(f)

    catalog_urns = {rc["urn"] for rc in catalog["objects"]["reference_controls"]}

    linked = skipped_other_family = skipped_missing = 0
    other_families = set()

    for node in profile["objects"]["framework"]["requirement_nodes"]:
        annotation = node.get("annotation")
        if not annotation:
            continue
        codes = CODE_RE.findall(annotation)
        if not codes:
            continue

        urns, missing, foreign = [], [], []
        for family, base, enhancement in codes:
            urn = code_to_urn(family, base, enhancement)
            if urn in catalog_urns:
                urns.append(urn)
            else:
                missing.append(f"{family}-{base}" + (f"({enhancement})" if enhancement else ""))
                foreign.append(family)

        if missing:
            skipped_other_family += 1
            other_families.update(foreign)
            print(f"skip {node['ref_id']:>3}: no catalog entry for {', '.join(missing)}")
            continue

        # de-dup, keep order
        seen = set()
        urns = [u for u in urns if not (u in seen or seen.add(u))]
        linked += 1
        if patch:
            node["reference_controls"] = urns
        else:
            print(f"link {node['ref_id']:>3}: {len(urns)} control(s)")

    print(
        f"\nlinked: {linked}, skipped (other family): {skipped_other_family} "
        f"({', '.join(sorted(other_families))})"
    )

    if patch:
        deps = profile.setdefault("dependencies", [])
        if CATALOG_URN not in deps:
            deps.append(CATALOG_URN)
        with open(PROFILE_PATH, "w") as f:
            yaml.dump(
                profile, f, allow_unicode=True, sort_keys=False, width=110,
                default_flow_style=False,
            )
        print(f"patched: {PROFILE_PATH}")


if __name__ == "__main__":
    main()
