from __future__ import annotations

from pathlib import Path
from typing import Any
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from docx import Document
from docx.document import Document as DocumentObject
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph


WORD_NAMESPACE = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def is_heading_style(style_name: str | None) -> bool:
    return bool(style_name and style_name.strip().lower().startswith("heading"))


def get_heading_level(style_name: str | None) -> int | None:
    if not style_name:
        return None

    parts = style_name.strip().split()
    if len(parts) < 2:
        return None

    try:
        return int(parts[-1])
    except ValueError:
        return None


def iter_document_blocks(document: DocumentObject) -> list[Paragraph | Table]:
    blocks: list[Paragraph | Table] = []

    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            blocks.append(Paragraph(child, document))
        elif child.tag == qn("w:tbl"):
            blocks.append(Table(child, document))

    return blocks


def extract_table_rows(table: Table) -> list[list[str]]:
    rows: list[list[str]] = []

    for row in table.rows:
        rows.append(["\n".join(cell.text.splitlines()).strip() for cell in row.cells])

    return rows


def extract_docx_comments(file_path: Path) -> list[dict[str, str | None]]:
    try:
        with ZipFile(file_path) as docx_package:
            try:
                comments_xml = docx_package.read("word/comments.xml")
            except KeyError:
                return []
    except BadZipFile:
        return []

    try:
        comments_root = ElementTree.fromstring(comments_xml)
    except ElementTree.ParseError:
        return []
    comments: list[dict[str, str | None]] = []

    for comment in comments_root.findall("w:comment", WORD_NAMESPACE):
        text_nodes = comment.findall(".//w:t", WORD_NAMESPACE)
        text = "".join(node.text or "" for node in text_nodes).strip()
        if not text:
            continue

        comments.append(
            {
                "id": comment.attrib.get(qn("w:id")),
                "author": comment.attrib.get(qn("w:author")),
                "date": comment.attrib.get(qn("w:date")),
                "text": text,
            }
        )

    return comments


def extract_docx(file_path: Path) -> dict[str, Any]:
    document = Document(file_path)
    text_sections: list[str] = []
    headings: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    paragraph_count = 0
    table_count = 0
    heading_count = 0

    for block in iter_document_blocks(document):
        if isinstance(block, Paragraph):
            paragraph_text = block.text.strip()
            if not paragraph_text:
                continue

            paragraph_count += 1
            style_name = block.style.name if block.style is not None else None

            if is_heading_style(style_name):
                heading_count += 1
                heading = {
                    "index": paragraph_count,
                    "text": paragraph_text,
                    "style": style_name,
                    "level": get_heading_level(style_name),
                }
                headings.append(heading)
                text_sections.append(f"[Heading: {paragraph_text}]")
            else:
                text_sections.append(paragraph_text)

        elif isinstance(block, Table):
            table_count += 1
            rows = extract_table_rows(block)
            tables.append({"index": table_count, "rows": rows})
            rendered_rows = [" | ".join(cell for cell in row) for row in rows]
            text_sections.append(
                "\n".join([f"[Table {table_count}]", *rendered_rows])
            )

    comments = extract_docx_comments(file_path)
    metadata = {
        "paragraph_count": paragraph_count,
        "table_count": table_count,
        "heading_count": heading_count,
        "comment_count": len(comments),
    }

    return {
        "text_content": "\n\n".join(text_sections),
        "json_content": {
            "headings": headings,
            "tables": tables,
            "comments": comments,
            "metadata": metadata,
        },
    }
