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
IMAGE_EXTENSION_BY_CONTENT_TYPE = {
    "image/bmp": "bmp",
    "image/gif": "gif",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/tiff": "tiff",
    "image/x-emf": "emf",
    "image/x-wmf": "wmf",
}
ENTERPRISE_STRUCTURE_TITLE = "Enterprise Structure"


def normalize_text(value: str) -> str:
    return " ".join(value.strip().split()).lower()


def is_enterprise_structure_text(value: str) -> bool:
    return normalize_text(value) == normalize_text(ENTERPRISE_STRUCTURE_TITLE)


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


def get_paragraph_image_relationship_ids(paragraph: Paragraph) -> list[str]:
    relationship_ids: list[str] = []

    for blip in paragraph._p.xpath(".//*[local-name()='blip']"):
        relationship_id = blip.get(qn("r:embed"))
        if relationship_id:
            relationship_ids.append(relationship_id)

    return relationship_ids


def get_image_extension(part: Any) -> str:
    content_type = getattr(part, "content_type", None)
    if isinstance(content_type, str) and content_type in IMAGE_EXTENSION_BY_CONTENT_TYPE:
        return IMAGE_EXTENSION_BY_CONTENT_TYPE[content_type]

    partname = getattr(part, "partname", None)
    suffix = Path(str(partname)).suffix.lower().removeprefix(".")
    return suffix or "bin"


def save_paragraph_images(
    document: DocumentObject,
    paragraph: Paragraph,
    image_output_dir: Path | None,
    image_storage_prefix: str | None,
    image_count: int,
    section_title: str | None,
) -> list[dict[str, Any]]:
    if image_output_dir is None or image_storage_prefix is None:
        return []

    saved_images: list[dict[str, Any]] = []
    relationship_ids = get_paragraph_image_relationship_ids(paragraph)

    if not relationship_ids:
        return []

    image_output_dir.mkdir(parents=True, exist_ok=True)

    for relationship_id in relationship_ids:
        part = document.part.related_parts.get(relationship_id)
        if part is None or not hasattr(part, "blob"):
            continue

        image_count += 1
        image_extension = get_image_extension(part)
        image_filename = f"image_{image_count:03d}.{image_extension}"
        image_path = image_output_dir / image_filename
        image_path.write_bytes(part.blob)
        storage_path = f"{image_storage_prefix}/{image_filename}"
        saved_images.append(
            {
                "index": image_count,
                "storage_path": storage_path,
                "section_title": section_title,
                "relationship_id": relationship_id,
            }
        )

    return saved_images


def extract_docx(
    file_path: Path,
    image_output_dir: Path | None = None,
    image_storage_prefix: str | None = None,
) -> dict[str, Any]:
    document = Document(file_path)
    text_sections: list[str] = []
    headings: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    image_paths: list[str] = []
    images: list[dict[str, Any]] = []
    paragraph_count = 0
    table_count = 0
    heading_count = 0
    image_count = 0
    current_section_title: str | None = None

    for block in iter_document_blocks(document):
        if isinstance(block, Paragraph):
            paragraph_text = block.text.strip()
            paragraph_images = save_paragraph_images(
                document=document,
                paragraph=block,
                image_output_dir=image_output_dir,
                image_storage_prefix=image_storage_prefix,
                image_count=image_count,
                section_title=current_section_title,
            )
            if paragraph_images:
                images.extend(paragraph_images)
                image_paths.extend(image["storage_path"] for image in paragraph_images)
                image_count = images[-1]["index"]
                text_sections.extend(
                    f"[Image: {image['storage_path']}]" for image in paragraph_images
                )

            if not paragraph_text:
                continue

            paragraph_count += 1
            style_name = block.style.name if block.style is not None else None

            if is_heading_style(style_name) or is_enterprise_structure_text(
                paragraph_text
            ):
                heading_count += 1
                heading = {
                    "index": paragraph_count,
                    "text": paragraph_text,
                    "style": style_name,
                    "level": get_heading_level(style_name),
                }
                headings.append(heading)
                current_section_title = paragraph_text
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
        "image_count": image_count,
        "comment_count": len(comments),
    }

    return {
        "text_content": "\n\n".join(text_sections),
        "json_content": {
            "headings": headings,
            "tables": tables,
            "images": images,
            "image_paths": image_paths,
            "comments": comments,
            "metadata": metadata,
        },
    }
