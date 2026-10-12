# /// script
# dependencies = ["python-pptx"]
# ///
"""Read a PowerPoint deck (.pptx): every slide's text, speaker notes and pictures.

Prints the deck as JSON (the default), plain text or Markdown. Each slide gives
its number, a title (the title placeholder, else the first line of text), the
text of each shape, the speaker notes and the pictures on it. Tables are read
cell by cell, row by row, with cells separated by " | ". The deck's document
properties (title, author, created, modified) come first.

Options:
  --output-format json|text|markdown   how to print (default json)
  --no-notes      leave out speaker notes
  --no-images     leave out picture details
  --text-only     leave out shape positions and types
  --output PATH   also write the result to this file

Example:
  python3 powerpoint_handler.py --ppt-file board-deck.pptx --output-format markdown
"""

import argparse
import json
import sys
from pathlib import Path


def fail(message, code=1):
    print(message, file=sys.stderr)
    sys.exit(code)


def shape_text(shape):
    if getattr(shape, "has_table", False) and shape.has_table:
        return "\n".join(" | ".join(cell.text.strip() for cell in row.cells)
                         for row in shape.table.rows)
    return shape.text.strip() if getattr(shape, "has_text_frame", False) else ""


def read_slide(slide, number, notes, images, text_only):
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    shapes, pictures = [], []
    for shape in slide.shapes:
        entry = {"text": shape_text(shape)}
        if not text_only:
            entry.update(type=str(shape.shape_type), left=shape.left, top=shape.top,
                         width=shape.width, height=shape.height)
        shapes.append(entry)
        if images and shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            pictures.append({"name": shape.name, "content_type": shape.image.content_type,
                             "bytes": len(shape.image.blob)})
    title_shape = slide.shapes.title
    title = title_shape.text.strip() if title_shape is not None and title_shape.text.strip() else None
    if title is None:
        title = next((s["text"].split("\n")[0][:100] for s in shapes if s["text"]), None)
    slide_notes = None
    if notes and slide.has_notes_slide:
        frame = slide.notes_slide.notes_text_frame  # None when the notes page has no body box
        slide_notes = (frame.text.strip() or None) if frame is not None else None
    return {"slide_number": number, "title": title, "shapes": shapes,
            "notes": slide_notes, "images": pictures}


def read_deck(path, notes=True, images=True, text_only=False):
    from pptx import Presentation

    if Path(path).suffix.lower() != ".pptx":
        fail(f"not a .pptx deck: {path}")
    if not Path(path).exists():
        fail(f"file not found: {path}")
    deck = Presentation(path)
    props = deck.core_properties
    metadata = {"title": props.title, "author": props.author, "subject": props.subject,
                "created": props.created.isoformat() if props.created else None,
                "modified": props.modified.isoformat() if props.modified else None,
                "last_modified_by": props.last_modified_by}
    slides = [read_slide(s, i, notes, images, text_only) for i, s in enumerate(deck.slides, 1)]
    return {"filename": Path(path).name, "slide_count": len(slides), "metadata": metadata,
            "slides": slides}


def as_text(deck, markdown):
    lines = [f"# {deck['filename']}" if markdown else f"Presentation: {deck['filename']}",
             f"Slides: {deck['slide_count']}", ""]
    for slide in deck["slides"]:
        lines.append(f"## Slide {slide['slide_number']}" if markdown else f"SLIDE {slide['slide_number']}")
        if slide["title"]:
            lines.append(f"Title: {slide['title']}")
        for shape in slide["shapes"]:
            if shape["text"]:
                lines.append(f"- {shape['text']}" if markdown else shape["text"])
        if slide["notes"]:
            lines += ["", "Speaker notes:", slide["notes"]]
        if slide["images"]:
            lines.append(f"Pictures: {len(slide['images'])}")
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read a PowerPoint deck's text and notes.")
    parser.add_argument("--ppt-file", "-p", required=True, help="the .pptx deck to read")
    parser.add_argument("--output-format", "-o", choices=["json", "text", "markdown"],
                        default="json")
    parser.add_argument("--no-notes", action="store_true", help="leave out speaker notes")
    parser.add_argument("--no-images", action="store_true", help="leave out picture details")
    parser.add_argument("--text-only", action="store_true", help="leave out shape positions")
    parser.add_argument("--output", help="also write the result to this file")
    args = parser.parse_args(argv)

    deck = read_deck(args.ppt_file, not args.no_notes, not args.no_images, args.text_only)
    if args.output_format == "json":
        out = json.dumps(deck, indent=2)
    else:
        out = as_text(deck, args.output_format == "markdown")
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
