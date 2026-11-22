"""Rebuild the two CSVs from the Group 5 reading materials and test items."""
import argparse
import csv
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile


DATA = Path(__file__).resolve().parent / "data"
WORD = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
PASSAGE_FIELDS = ["passage_id", "title", "genre", "tier", "words", "target_skill",
                  "new_vocabulary", "text"]
QUESTION_FIELDS = ["question_id", "passage_id", "mode", "question", "answer", "rubric"]
WORD_HEADINGS = ["ID", "Mode", "Question", "Answer", "One point awarded when"]
MATERIAL_HEADINGS = ["ID", "Genre", "Title", "Tier", "Words", "Target skill", "New vocabulary"]


def document_tables(path):
    with ZipFile(path) as doc:
        root = ET.fromstring(doc.read("word/document.xml"))
    return root.findall("w:body/w:tbl", WORD)


def table_rows(table):
    rows = []
    for row in table.findall("w:tr", WORD):
        cells = []
        for cell in row.findall("w:tc", WORD):
            paragraphs = []
            for paragraph in cell.findall("w:p", WORD):
                runs = paragraph.findall(".//w:t", WORD)
                paragraphs.append("".join(run.text or "" for run in runs))
            cells.append("\n".join(paragraphs))
        rows.append(cells)
    return rows


def read_bank(source_dir):
    materials = document_tables(source_dir / "INFH5000_Group5_Reading_Materials.docx")
    headings, *metadata = table_rows(materials[0])
    if headings != MATERIAL_HEADINGS:
        raise ValueError("Unexpected columns in the reading materials table.")
    by_id = {row[0]: row for row in metadata}
    expected_ids = {f"{genre}{tier}" for genre in "NID" for tier in range(1, 6)}
    if set(by_id) != expected_ids or len(metadata) != len(expected_ids):
        raise ValueError("Expected one metadata record per appendix passage.")
    # The mastery-band table is followed by one passage and one item table per text.
    tables = document_tables(source_dir / "INFH5000_Group5_Test_Items.docx")
    if len(tables) != 1 + 2 * len(metadata) or table_rows(tables[0])[0][0] != "Band":
        raise ValueError("Unexpected table layout in the assessment appendix.")

    passages, questions = [], []
    seen = set()
    for passage_table, item_table in zip(tables[1::2], tables[2::2]):
        [[passage_cell]] = table_rows(passage_table)
        heading, text = passage_cell.split("\n", 1)
        passage_id = heading.removeprefix("Passage ")
        if passage_id not in by_id or passage_id in seen or not text.strip():
            raise ValueError(f"Invalid or duplicated passage: {heading}")
        seen.add(passage_id)
        _, genre, title, tier, words, skill, vocab = by_id[passage_id]
        vocabulary = [] if vocab == "none" else [word.strip() for word in vocab.split(",")]
        passages.append([passage_id, title, genre, tier, words, skill,
                         json.dumps(vocabulary, ensure_ascii=False), text])

        headings, *items = table_rows(item_table)
        expected_count = 14 if passage_id.startswith("D") else 13
        if headings != WORD_HEADINGS or len(items) != expected_count:
            raise ValueError(f"{passage_id}: unexpected question columns or count.")
        for number, row in enumerate(items, 1):
            qid, mode, question, answer, rubric = row
            if qid != f"{passage_id}.{number}" or not all(cell.strip() for cell in row):
                raise ValueError(f"{passage_id}, item {number}: invalid ID or empty cell.")
            if mode not in {"oral", "choice", "written"}:
                raise ValueError(f"{qid}: unknown response mode {mode!r}.")
            if mode == "choice":
                labels = re.findall(r"\b([A-D])\.\s+", question)
                if labels != list("ABCD") or answer not in labels:
                    raise ValueError(f"{qid}: invalid choice options or answer key.")
            questions.append([qid, passage_id, mode, question, answer, rubric])
    return passages, questions


def export_bank(source_dir, data=DATA):
    passages, questions = read_bank(source_dir)
    exports = [("passages.csv", PASSAGE_FIELDS, passages),
               ("questions.csv", QUESTION_FIELDS, questions)]
    with TemporaryDirectory(dir=data) as staging:
        for filename, header, rows in exports:
            path = Path(staging) / filename
            with path.open("w", encoding="utf-8", newline="") as output:
                writer = csv.writer(output, lineterminator="\n")
                writer.writerow(header)
                writer.writerows(rows)
        for filename, _, _ in exports:
            (Path(staging) / filename).replace(data / filename)
    print(f"Exported {len(passages)} passages and {len(questions)} questions to {data}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DATA.parent.parent,
                        help="folder containing the two course Word documents (default: project folder)")
    args = parser.parse_args()
    try:
        export_bank(args.source_dir)
    except (ValueError, FileNotFoundError) as error:
        parser.exit(1, f"{error}\n")
