#!/usr/bin/env python3
"""Generate assessment questions for DSSZZI base security profile requirements
from ODP parameters of the ND TZI 3.6 controls catalog.

For every assessable requirement the annotation lists catalog control refs
(e.g. "AC-2, AC-2(5)"). Each parameter of those controls becomes a question:
  [Вибір ...]        -> unique_choice / multiple_choice (dropdown in audit UI)
  [Призначення ...]  -> text (organization-defined value)

Usage:
  python3 generate_questions.py                 # preview
  python3 generate_questions.py --patch         # write questions into framework YAML
"""
import re
import sys

import yaml

from extract_parameters import find_parameters, dedupe

CATALOG = "nd-tzi-3-6-controls-ac-pilot.yaml"
FRAMEWORK = "dsszzi-base-security-profile.yaml"
CONTROL_REF_RE = re.compile(r"\b([A-Z]{2}-\d+(?:\(\d+\))?)")


def build_questions(req: dict, params_by_ref: dict) -> dict:
    """Return {question_urn: question_dict} for one requirement node."""
    refs = []
    for ref in CONTROL_REF_RE.findall(req.get("annotation", "") or ""):
        if ref in params_by_ref and ref not in refs:
            refs.append(ref)

    questions = {}
    seen = set()
    n = 0
    for ref in refs:
        for p in params_by_ref[ref]:
            key = (p["kind"], p["body"])
            if key in seen:
                continue
            seen.add(key)
            n += 1
            q_urn = f"{req['urn']}:question:{n}"
            if p["kind"] == "selection":
                q = {
                    "type": "multiple_choice" if p["multiple"] else "unique_choice",
                    "text": f"{ref} — {p['label']}: оберіть значення",
                    "choices": [
                        {"urn": f"{q_urn}:choice:{i}", "value": choice}
                        for i, choice in enumerate(p["choices"], 1)
                    ],
                }
            else:
                q = {
                    "type": "text",
                    "text": f"{ref} — {p['label']}: {p['body']} — вкажіть значення",
                }
            questions[q_urn] = q
    return questions


def main() -> None:
    patch = "--patch" in sys.argv

    catalog = yaml.safe_load(open(CATALOG))
    params_by_ref = {}
    for rc in catalog["objects"]["reference_controls"]:
        desc = (rc.get("description") or "").split("Параметри:")[0]
        params = dedupe(find_parameters(desc))
        if params:
            params_by_ref[rc["ref_id"]] = params

    fw = yaml.safe_load(open(FRAMEWORK))
    reqs = fw["objects"]["framework"]["requirement_nodes"]

    total_q = total_req = 0
    for req in reqs:
        if not req.get("assessable"):
            continue
        questions = build_questions(req, params_by_ref)
        if not questions:
            continue
        total_req += 1
        total_q += len(questions)
        if patch:
            req["questions"] = questions
        else:
            print(f"== {req['ref_id']}. {req['name']} ({len(questions)})")
            for urn, q in questions.items():
                print(f"   [{q['type']}] {q['text'][:100]}")
                for c in q.get("choices", []):
                    print(f"      - {c['value'][:90]}")

    print(f"\nrequirements with questions: {total_req}, questions total: {total_q}")

    if patch:
        with open(FRAMEWORK, "w") as f:
            yaml.dump(
                fw, f, allow_unicode=True, sort_keys=False, width=110,
                default_flow_style=False,
            )
        print(f"patched: {FRAMEWORK}")


if __name__ == "__main__":
    main()
