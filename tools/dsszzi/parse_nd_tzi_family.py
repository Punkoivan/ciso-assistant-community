#!/usr/bin/env python3
"""Parse one control family from the ND TZI 3.6-006-24 text dump
(pdftotext output of the official PDF) into reference_controls entries.

Usage:
  python3 parse_nd_tzi_family.py <full_text.txt> <FAMILY> > preview.yaml

Section layout in the document (chapter 10):
  10.N Клас заходів захисту XX — NAME
  XX-1 CONTROL NAME (caps, may wrap)
  Заходи захисту: ...            -> description
  Рекомендації з реалізації: ... -> annotation
  Пов'язані заходи: ...          -> dropped (kept in source)
  Посилення заходів:             -> enhancements (N) NAME ... same structure
  Посилання: ...                 -> dropped
Withdrawn controls/enhancements ("[Вилучено ...]") keep empty description,
matching the AC pilot convention.
"""
import re
import sys

import yaml

URN_ROOT = "urn:intuitem:risk:library:dsszzi-nd-tzi-3-6-controls"

# Cyrillic lookalikes sometimes used in control ids in the document
LOOKALIKES = str.maketrans("АВСЕІКМНОРТХУ", "ABCEIKMHOPTXY")

MARKER_RE = re.compile(r"^(?:[a-zа-я]\.|\d{1,2}\.|\([a-zа-я]\)|\(\d{1,2}\))$")
PAGE_RE = re.compile(r"^\d{1,3}$")


def latinize(ref: str) -> str:
    return ref.translate(LOOKALIKES)


def sentence(part: str) -> str:
    part = part.strip()
    if not part:
        return part
    low = part.lower()
    return low[0].upper() + low[1:]


def pretty_name(raw: str, base_name: str | None = None) -> str:
    """Sentence-case a caps header; enhancements become 'База — Посилення'."""
    raw = re.sub(r"\s+", " ", raw).strip()
    parts = re.split(r"\s+[-–—]\s+", raw)
    if base_name and len(parts) == 1:
        return f"{base_name} — {sentence(parts[0])}"
    named = [sentence(p) for p in parts]
    return " — ".join(named)


def reflow(text: str) -> str:
    """Join wrapped lines into paragraphs, keep list items separated."""
    paragraphs = []
    buf: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line or PAGE_RE.match(line):
            if buf:
                paragraphs.append(" ".join(buf))
                buf = []
            continue
        buf.append(line)
    if buf:
        paragraphs.append(" ".join(buf))
    # glue marker-only paragraphs ("a.", "1.", "(a)") to the following one
    glued: list[str] = []
    for p in paragraphs:
        if glued and MARKER_RE.match(glued[-1]):
            glued[-1] = f"{glued[-1]} {p}"
        elif glued and MARKER_RE.match(p.split(" ")[0]) and len(p.split(" ")) == 1:
            glued.append(p)
        else:
            glued.append(p)
    return "\n\n".join(glued).strip()


def split_sections(block: str) -> tuple[str, str]:
    """Return (description, annotation) from a control/enhancement body."""
    desc, annot = block, ""
    m = re.search(r"Рекомендації з реалізації:", block)
    if m:
        desc = block[: m.start()]
        annot = block[m.end():]
        stop = re.search(r"Пов[’'ʼ]язані заходи:|Посилення заходів:|Посилання:", annot)
        if stop:
            annot = annot[: stop.start()]
    else:
        stop = re.search(r"Пов[’'ʼ]язані заходи:|Посилення заходів:|Посилання:", desc)
        if stop:
            desc = desc[: stop.start()]
    desc = re.sub(r"^\s*Заходи захисту:\s*", "", desc.strip())
    return reflow(desc), reflow(annot)


def _glue_standalone_refs(section: str, family_class: str) -> str:
    """From the IA section onward the ref sometimes stands alone on its
    line, with the (possibly multi-line, all-caps) control name wrapping
    below it instead of following on the same line:

        ІА-2

        ІДЕНТИФІКАЦІЯ ТА АВТЕНТИФІКАЦІЯ (КОРИСТУВАЧІВ ОРГАНІЗАЦІЇ)
        Заходи захисту:

    Rejoin these onto a single "REF NAME" line so ctrl_re (which expects
    the name on the same line, as in the AC..CP sections) can match them.
    """
    ref_alone_re = re.compile(rf"^{family_class}-\d+$")
    lines = section.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        if ref_alone_re.match(ln):
            j = i + 1
            name_lines: list[str] = []
            while j < len(lines):
                nxt = lines[j].strip()
                if not nxt:
                    if name_lines:
                        break
                    j += 1
                    continue
                if nxt.upper() == nxt and re.search(r"[А-ЯЄІЇҐA-Z]", nxt) and not nxt.startswith("Заходи"):
                    name_lines.append(nxt)
                    j += 1
                else:
                    break
            if name_lines:
                out.append(f"{ln} {' '.join(name_lines)}")
                i = j
                continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def parse_family(full_text: str, family: str) -> list[dict]:
    # pdftotext marks page breaks with form feeds glued to the next line;
    # with -layout every line also carries positional indentation — drop both
    lines = [ln.lstrip("\x0c").strip() for ln in full_text.split("\n")]
    # real section headers are followed by a control header within a few lines;
    # this drops table-of-contents entries which match the same pattern
    # the ref may stand alone on its line, with the control name wrapping
    # to the next line (seen from the IA section onward)
    any_ctrl_re = re.compile(r"^[A-ZА-ЯЄІЇҐ]{2}-\d+(\s|$)")
    starts = [
        i for i, ln in enumerate(lines)
        if re.match(r"^10\.\d+\s+Клас\s+заходів\s+захисту", ln)
        and any(any_ctrl_re.match(lines[j]) for j in range(i + 1, min(i + 8, len(lines))))
    ]
    section = None
    for idx, i in enumerate(starts):
        m = re.match(r"^10\.\d+\s+Клас\s+заходів\s+захисту\s+(\S+)", lines[i])
        if m and latinize(m.group(1).upper()) == family:
            end = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
            section = "\n".join(lines[i + 1 : end])
            break
    if section is None:
        raise SystemExit(f"family {family} section not found")

    # split into base controls; the ref itself may use Cyrillic lookalikes
    # (e.g. "СР-1" for "CP-1"), so match either script per letter
    cyr_for_latin = {l: c for c, l in zip("АВСЕІКМНОРТХУ", "ABCEIKMHOPTXY")}
    family_class = "".join(
        f"[{ch}{cyr_for_latin[ch]}]" if ch in cyr_for_latin else re.escape(ch)
        for ch in family
    )
    section = _glue_standalone_refs(section, family_class)
    ctrl_re = re.compile(
        rf"^({family_class}-\d+) *([А-ЯЄІЇҐA-Z].*)$", re.MULTILINE
    )
    matches = list(ctrl_re.finditer(section))
    controls = []
    for k, m in enumerate(matches):
        end = matches[k + 1].start() if k + 1 < len(matches) else len(section)
        controls.append((latinize(m.group(1)), m.group(2), section[m.end():end]))

    entries = []
    for ref, name_first, body in controls:
        # header may wrap: caps lines before first structural marker belong to name
        name_lines = [name_first]
        if body.startswith("\n"):  # line terminator of the header itself
            body = body[1:]
        rest_lines = body.split("\n")
        while rest_lines:
            ln = rest_lines[0].strip()
            if ln and not ln.startswith(("Заходи захисту", "[Вилучено")) and (
                ln.upper() == ln
            ) and not PAGE_RE.match(ln) and not re.match(r"^\(\d+\)", ln):
                name_lines.append(ln)
                rest_lines.pop(0)
            else:
                break
        body = "\n".join(rest_lines)
        base_name = pretty_name(" ".join(name_lines))

        enh_split = re.search(r"^Посилення заходів:", body, re.MULTILINE)
        base_body = body[: enh_split.start()] if enh_split else body
        enh_body = body[enh_split.end():] if enh_split else ""

        if "[Вилучено" in base_body.split("Заходи захисту")[0]:
            entries.append(_entry(ref, base_name, withdrawal_note(base_body), ""))
        else:
            desc, annot = split_sections(base_body)
            entries.append(_entry(ref, base_name, desc, annot))

        # enhancements: "(N) NAME" or "(N)" alone with the CAPS name below;
        # "(N)" followed by mixed-case text is a list item, not a header
        enh_re = re.compile(r"^\((\d+)\)[ \t]*(.*)$", re.MULTILINE)
        ems = []
        for m in enh_re.finditer(enh_body):
            title = m.group(2).strip()
            if title:
                if title.upper() == title and re.search(r"[А-ЯЄІЇҐA-Z]", title):
                    ems.append(m)
                continue
            # a page break can drop a lone page number between the "(N)"
            # marker and its name line (e.g. "(8)\n174\n\nNAME...");
            # skip such page-number-only lines before giving up
            after_lines = enh_body[m.end():].split("\n")
            idx = 0
            while idx < len(after_lines) and (
                not after_lines[idx].strip() or PAGE_RE.match(after_lines[idx].strip())
            ):
                idx += 1
            nxt = after_lines[idx].strip() if idx < len(after_lines) else ""
            if nxt and nxt.upper() == nxt and re.search(r"[А-ЯЄІЇҐA-Z]", nxt):
                ems.append(m)
        for k, m in enumerate(ems):
            end = ems[k + 1].start() if k + 1 < len(ems) else len(enh_body)
            chunk = enh_body[m.end():end]
            e_name_lines = [m.group(2)] if m.group(2).strip() else []
            if chunk.startswith("\n"):  # line terminator of the "(N)" line
                chunk = chunk[1:]
            chunk_lines = chunk.split("\n")
            while chunk_lines:
                ln = chunk_lines[0].strip()
                if not ln or PAGE_RE.match(ln):
                    # skip blanks and page-break page numbers between the
                    # "(N)" marker and its CAPS name, but one of those
                    # after the name has started ends it
                    if e_name_lines:
                        break
                    chunk_lines.pop(0)
                    continue
                if ln.upper() == ln and not (
                    ln.startswith("[Вилучено")
                ):
                    e_name_lines.append(ln)
                    chunk_lines.pop(0)
                else:
                    break
            chunk = "\n".join(chunk_lines)
            e_ref = f"{ref}({m.group(1)})"
            e_name = pretty_name(" ".join(e_name_lines))
            if "[Вилучено" in chunk[:200]:
                entries.append(_entry(e_ref, e_name, withdrawal_note(chunk), ""))
            else:
                desc, annot = split_sections(chunk)
                entries.append(_entry(e_ref, e_name, desc, annot))
    return entries


WITHDRAWAL_RE = re.compile(r"\[Вилучено:?\s*([^\]]*)\]", re.IGNORECASE)
# a control ref mentioned inside the withdrawal note may itself use Cyrillic
# lookalikes ("СР-4"); only normalize tokens shaped like a ref, not the
# whole sentence — blanket latinize() would corrupt ordinary Cyrillic words
REF_TOKEN_RE = re.compile(r"\b[A-ZА-ЯЄІЇҐ]{2,3}-\d+(?:\(\d+\))?\b")


def withdrawal_note(text: str) -> str:
    """Keep the withdrawal reason (e.g. "Включено до CP-4") instead of
    discarding it — a bare empty stub looks indistinguishable from a
    parser miss."""
    m = WITHDRAWAL_RE.search(text)
    if not m:
        return ""
    body = re.sub(r"\s+", " ", m.group(1)).strip()
    body = REF_TOKEN_RE.sub(lambda r: latinize(r.group(0)), body)
    return f"Вилучено: {body}." if body else "Вилучено."


def _entry(ref: str, name: str, desc: str, annot: str) -> dict:
    urn_ref = ref.lower().replace("(", ".").replace(")", "")
    e = {
        "urn": f"{URN_ROOT}:{urn_ref}",
        "ref_id": ref,
        "name": name,
    }
    if desc:
        e["description"] = desc
    if annot:
        e["annotation"] = annot
    return e


def main() -> None:
    full_text = open(sys.argv[1]).read()
    family = sys.argv[2].upper()
    entries = parse_family(full_text, family)
    yaml.dump(
        entries, sys.stdout, allow_unicode=True, sort_keys=False, width=110,
        default_flow_style=False,
    )
    print(f"# parsed: {len(entries)} controls", file=sys.stderr)


if __name__ == "__main__":
    main()
