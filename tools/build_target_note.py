#!/usr/bin/env python3
"""Build the technical PDF from Markdown with Pandoc, ReportLab and svglib."""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

import matplotlib as mpl
from matplotlib.font_manager import FontProperties, findfont
from matplotlib.mathtext import math_to_image
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer
from svglib.svglib import svg2rlg

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/TARGET_THEORY.pdf")
    parser.add_argument("--ref", default="feat/target-observability")
    args = parser.parse_args()
    source = ROOT / "docs/TARGET_THEORY.md"
    text = source.read_text(encoding="utf-8")
    text = re.sub(r"```math\n(.*?)\n```", r"$$\n\1\n$$", text, flags=re.S)
    ast = json.loads(
        subprocess.check_output(
            ["pandoc", "--from=markdown+tex_math_dollars", "-t", "json"],
            input=text,
            text=True,
        )
    )
    for name, family, weight, style in (
        ("Body", "DejaVu Serif", "normal", "normal"),
        ("Body-Bold", "DejaVu Serif", "bold", "normal"),
        ("Body-Italic", "DejaVu Serif", "normal", "italic"),
        ("Body-BoldItalic", "DejaVu Serif", "bold", "italic"),
        ("Mono", "DejaVu Sans Mono", "normal", "normal"),
    ):
        pdfmetrics.registerFont(
            TTFont(
                name,
                findfont(FontProperties(family=family, weight=weight, style=style)),
            )
        )
    pdfmetrics.registerFontFamily(
        "Body",
        normal="Body",
        bold="Body-Bold",
        italic="Body-Italic",
        boldItalic="Body-BoldItalic",
    )
    styles = {
        "body": ParagraphStyle(
            "body",
            fontName="Body",
            fontSize=10,
            leading=13,
            spaceAfter=6,
            allowWidows=0,
            allowOrphans=0,
        ),
        "heading": ParagraphStyle(
            "heading",
            fontName="Body-Bold",
            fontSize=12.5,
            leading=17,
            spaceBefore=11,
            spaceAfter=6,
            keepWithNext=True,
        ),
        "title": ParagraphStyle(
            "title", fontName="Body-Bold", fontSize=20, leading=25, spaceAfter=10
        ),
    }
    styles["before-equation"] = ParagraphStyle(
        "before-equation", parent=styles["body"], keepWithNext=True
    )
    width = A4[0] - 108
    inline_cache = {}

    def inline_math(tex):
        if tex not in inline_cache:
            path = Path(math_directory) / f"equation-{len(inline_cache)}.png"
            with mpl.rc_context({"mathtext.fontset": "dejavuserif"}):
                math_to_image(
                    "$" + " ".join(tex.split()) + "$",
                    path,
                    prop=FontProperties(size=10),
                    dpi=300,
                    format="png",
                )
            w, h = ImageReader(str(path)).getSize()
            inline_cache[tex] = (
                f'<img src={quoteattr(str(path))} width="{w * 72 / 300:.3f}" '
                f'height="{h * 72 / 300:.3f}" valign="middle"/>'
            )
        return inline_cache[tex]

    def inline(nodes):
        parts = []
        for index, node in enumerate(nodes):
            kind, value = node["t"], node.get("c")
            if kind == "Str":
                if index and nodes[index - 1]["t"] == "Math":
                    parts[-1] = "<nobr>" + parts[-1] + escape(value) + "</nobr>"
                else:
                    parts.append(escape(value))
            elif kind in ("Space", "SoftBreak"):
                parts.append(" ")
            elif kind == "LineBreak":
                parts.append("<br/>")
            elif kind == "Math":
                parts.append(inline_math(value[1]))
            elif kind in ("Superscript", "Subscript"):
                tag = "super" if kind == "Superscript" else "sub"
                parts.append(f"<{tag}>" + inline(value) + f"</{tag}>")
            elif kind in ("Strong", "Emph"):
                tag = "b" if kind == "Strong" else "i"
                parts.append(f"<{tag}>" + inline(value) + f"</{tag}>")
            elif kind == "Code":
                parts.append(
                    '<font name="Mono" size="8.8">' + escape(value[1]) + "</font>"
                )
            elif kind == "Link":
                url = value[2][0]
                if not url.startswith(("https://", "http://")):
                    url = (
                        "https://github.com/yeruciwenrou-dotcom/homological-observability/blob/"
                        + args.ref
                        + "/docs/"
                        + url
                    )
                parts.append(
                    "<link href="
                    + quoteattr(url)
                    + ' color="#28537d">'
                    + inline(value[1])
                    + "</link>"
                )
            else:
                raise ValueError("Unsupported inline: " + kind)
        return "".join(parts)

    def equation(tex):
        tex = tex.replace(r"\frac12", r"\frac{1}{2}")
        tex = tex.replace(
            r"\begin{bmatrix}P\\F\end{bmatrix}", r"\left[\genfrac{}{}{0}{}{P}{F}\right]"
        )
        buffer = io.BytesIO()
        with mpl.rc_context(
            {"mathtext.fontset": "dejavuserif", "svg.fonttype": "path"}
        ):
            math_to_image(
                "$" + " ".join(tex.split()) + "$",
                buffer,
                prop=FontProperties(size=12),
                format="svg",
            )
        buffer.seek(0)
        drawing = svg2rlg(buffer)
        factor = min(1, width / drawing.width)
        drawing.scale(factor, factor)
        drawing.width *= factor
        drawing.height *= factor
        drawing.hAlign = "CENTER"
        return drawing

    story = []

    def is_equation(block):
        return (
            block["t"] in ("Para", "Plain")
            and len(block["c"]) == 1
            and block["c"][0]["t"] == "Math"
        )

    def blocks(values, bullet=False):
        for index, block in enumerate(values):
            kind, value = block["t"], block.get("c")
            if kind == "Header":
                heading = inline(value[2])
                if value[0] == 1:
                    heading = heading.replace(": ", ":<br/>", 1)
                story.append(
                    Paragraph(
                        heading,
                        styles["title" if value[0] == 1 else "heading"],
                    )
                )
            elif kind in ("Para", "Plain"):
                if is_equation(block):
                    story.extend([equation(value[0]["c"][1]), Spacer(1, 8)])
                else:
                    style = (
                        "before-equation"
                        if index + 1 < len(values) and is_equation(values[index + 1])
                        else "body"
                    )
                    paragraph = Paragraph(
                        inline(value),
                        styles[style],
                        bulletText="•" if bullet else None,
                    )
                    ends_section = (
                        index + 1 < len(values) and values[index + 1]["t"] == "Header"
                    )
                    story.append(
                        KeepTogether([paragraph]) if ends_section else paragraph
                    )
            elif kind == "BulletList":
                for item in value:
                    blocks(item, bullet=True)
            else:
                raise ValueError("Unsupported block: " + kind)

    with tempfile.TemporaryDirectory(prefix="target-note-") as math_directory:
        blocks(ast["blocks"])
        args.output.parent.mkdir(parents=True, exist_ok=True)
        SimpleDocTemplate(
            str(args.output),
            pagesize=A4,
            leftMargin=54,
            rightMargin=54,
            topMargin=48,
            bottomMargin=48,
            title="Target observability: technical derivation",
            author="",
            invariant=1,
        ).build(story)
    print(args.output)


if __name__ == "__main__":
    main()
