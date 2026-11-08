#!/usr/bin/env python3
"""Build the technical PDF from Markdown with XeLaTeX."""

import argparse
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK_ROOT = (
    "https://github.com/yeruciwenrou-dotcom/homological-observability/blob/v2.1.0/docs/"
)
ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}
TOKENS = re.compile(r"(\$[^$]+\$|`[^`]+`|\*\*.+?\*\*|\[[^\]]+\]\([^)]+\))")


def escape(text):
    return "".join(ESCAPES.get(c, c) for c in text)


def math(tex):
    return tex.replace(r"\mathrm{rank}", r"\operatorname{rank}")


def inline(text):
    result = []
    for token in TOKENS.split(text):
        if token.startswith("$") and token.endswith("$"):
            result.append("$" + math(token[1:-1]) + "$")
        elif token.startswith("`") and token.endswith("`"):
            result.append(r"\texttt{" + escape(token[1:-1]) + "}")
        elif token.startswith("**") and token.endswith("**"):
            result.append(r"\textbf{" + inline(token[2:-2]) + "}")
        elif re.fullmatch(r"\[[^\]]+\]\([^)]+\)", token):
            label, url = re.fullmatch(r"\[([^\]]+)\]\(([^)]+)\)", token).groups()
            if not url.startswith(("https://", "http://")):
                url = LINK_ROOT + url
            result.append(
                r"\href{"
                + url.replace("#", r"\#").replace("%", r"\%")
                + "}{"
                + inline(label)
                + "}"
            )
        else:
            result.append(escape(token))
    return "".join(result)


def parse(text):
    lines = text.splitlines()
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line in ("$$", "```math", "```text"):
            closing = "$$" if line == "$$" else "```"
            kind = "code" if line == "```text" else "math"
            data = []
            i += 1
            while i < len(lines) and lines[i].strip() != closing:
                data.append(lines[i])
                i += 1
            if i == len(lines):
                raise ValueError("Unclosed block")
            blocks.append((kind, "\n".join(data)))
        elif line.startswith("## "):
            blocks.append(("section", line[3:]))
        elif line.startswith("# "):
            blocks.append(("title", line[2:]))
        else:
            kind = "item" if line.startswith("- ") else "para"
            data = [line[2:] if kind == "item" else line]
            i += 1
            while (
                i < len(lines)
                and lines[i].strip()
                and not re.match(r"^(#|\$\$|```|- )", lines[i])
            ):
                data.append(lines[i].strip())
                i += 1
            blocks.append((kind, " ".join(data)))
            continue
        i += 1
    return blocks


def equation_label(tex):
    compact = re.sub(r"\s+", "", tex)
    if compact.startswith(r"\ker_{\mathbb{Z}}P"):
        return "eq:sufficiency"
    if compact.startswith("p'=Ax-Ah=Pc"):
        return "eq:open-path-decoder"
    if compact.startswith("F(c_0)+M"):
        return "eq:ambiguity-image"
    if compact.startswith(r"H(FC\midS,PC)=") and r"\sum" in tex:
        return "eq:target-entropy"
    return None


def convert(text):
    blocks = parse(text)
    output = []
    in_list = False
    labels = []
    for i, (kind, value) in enumerate(blocks):
        if in_list and kind != "item":
            output.append(r"\end{evidencelist}")
            in_list = False
        if kind == "title":
            output.append(r"\notetitle{" + inline(value) + "}")
        elif kind == "section":
            number, title = value.split(". ", 1)
            output.append(r"\section{" + inline(title) + r"}\label{sec:" + number + "}")
        elif kind == "math":
            label = equation_label(value)
            env = "equation" if label else "equation*"
            output.append(r"\begin{" + env + "}")
            if label:
                labels.append(label)
                output.append(r"\label{" + label + "}")
            output.extend([math(value), r"\end{" + env + "}"])
            if (
                i + 1 < len(blocks)
                and blocks[i + 1][0] == "para"
                and not blocks[i + 1][1].startswith("is nonnegative")
            ):
                output.append(r"\par")
        elif kind == "item":
            if not in_list:
                output.append(r"\begin{evidencelist}")
                in_list = True
            lead = re.match(r"^(`[^`]+`[:：])\s*(.*)$", value)
            if lead:
                output.append(
                    r"\item " + inline(lead[1]) + r"\nopagebreak\par " + inline(lead[2])
                )
            else:
                output.append(r"\item " + inline(value))
        elif kind == "code":
            output.append(r"\codesample{" + escape(value) + "}")
        else:
            paragraph = inline(value)
            paragraph = paragraph.replace("section 1.", r"section~\hyperref[sec:1]{1}.")
            if value.startswith("An open walk chain"):
                paragraph = r"\looseness=-1 " + paragraph
            if value.startswith("Known endpoints therefore"):
                paragraph = paragraph.replace(
                    r"zero. \texttt{record\_kind=", r"zero.\\* \texttt{record\_kind="
                )
            if value.startswith(
                ("Both inclusions follow", "The global coefficient is available")
            ):
                paragraph = (
                    r"\begingroup\clubpenalties 5 10000 10000 10000 10000 0\relax "
                    + paragraph
                    + r"\par\endgroup"
                )
            following_math = i + 1 < len(blocks) and blocks[i + 1][0] == "math"
            continuation = (
                i and blocks[i - 1][0] == "math" and value.startswith("is nonnegative")
            )
            output.append((r"\noindent " if continuation else "") + paragraph)
            if not following_math:
                output.append(r"\par")
    if in_list:
        output.append(r"\end{evidencelist}")
    assert labels == [
        "eq:sufficiency",
        "eq:open-path-decoder",
        "eq:ambiguity-image",
        "eq:target-entropy",
    ]
    assert sum(kind == "section" for kind, _ in blocks) == 7
    return "\n".join(output)


def latex_document(text):
    title = parse(text)[0][1]
    return "\n".join(
        [
            r"\documentclass[11pt,a4paper]{article}",
            r"\newcommand{\notemargin}{20mm}",
            r"\usepackage{note-style}",
            "",
            r"\hypersetup{pdftitle={" + escape(title) + "},pdfauthor={},pdfsubject={}}",
            r"\begin{document}",
            convert(text),
            r"\end{document}",
            "",
        ]
    )


def main():
    global LINK_ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/TARGET_THEORY.pdf")
    parser.add_argument("--ref", default="v2.1.0")
    parser.add_argument("--tex-bin", type=Path)
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build/target-note")
    args = parser.parse_args()
    LINK_ROOT = (
        "https://github.com/yeruciwenrou-dotcom/homological-observability/blob/"
        + args.ref
        + "/docs/"
    )
    engine = str(args.tex_bin / "xelatex") if args.tex_bin else shutil.which("xelatex")
    if not engine:
        raise SystemExit("XeLaTeX is required to rebuild the PDF.")
    build = args.build_dir.resolve()
    build.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "docs/note-style.sty", build / "note-style.sty")
    text = (ROOT / "docs/TARGET_THEORY.md").read_text(encoding="utf-8")
    (build / "TARGET_THEORY.tex").write_text(latex_document(text), encoding="utf-8")
    for _ in range(2):
        result = subprocess.run(
            [
                engine,
                "-interaction=nonstopmode",
                "-halt-on-error",
                "-file-line-error",
                "TARGET_THEORY.tex",
            ],
            cwd=build,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        (build / "TARGET_THEORY.build.log").write_text(result.stdout, encoding="utf-8")
        if result.returncode:
            raise SystemExit(result.stdout[-6000:])
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output != build / "TARGET_THEORY.pdf":
        shutil.copy2(build / "TARGET_THEORY.pdf", output)
    print(output)


if __name__ == "__main__":
    main()
