from __future__ import annotations

from typing import Any

BASE_DOCS = [
    (
        "python-venv",
        "The venv module creates lightweight Python virtual environments.",
        "Python uses the venv module for virtual environments.",
        ["venv", "virtual environments"],
    ),
    (
        "python-json",
        "The json module encodes and decodes JSON documents.",
        "Python uses the json module for JSON documents.",
        ["json", "JSON documents"],
    ),
    (
        "python-asyncio",
        "The asyncio module supports concurrent code with async and await syntax.",
        "Python uses asyncio for async concurrency.",
        ["asyncio", "async concurrency"],
    ),
    (
        "python-pathlib",
        "The pathlib module represents filesystem paths as objects.",
        "Python uses pathlib for object-oriented filesystem paths.",
        ["pathlib", "filesystem paths"],
    ),
    (
        "python-datetime",
        "The datetime module supplies classes for manipulating dates and times.",
        "Python uses datetime for dates and times.",
        ["datetime", "dates and times"],
    ),
    (
        "python-logging",
        "The logging module provides flexible event logging for applications.",
        "Python uses logging for application event logs.",
        ["logging", "event logs"],
    ),
    (
        "python-sqlite3",
        "The sqlite3 module provides a DB-API interface for SQLite databases.",
        "Python uses sqlite3 for SQLite database access.",
        ["sqlite3", "SQLite database"],
    ),
    (
        "python-unittest",
        "The unittest module supports test automation and shared setup code.",
        "Python uses unittest for test automation.",
        ["unittest", "test automation"],
    ),
    (
        "python-dataclasses",
        "The dataclasses module generates special methods for data containers.",
        "Python uses dataclasses for structured data containers.",
        ["dataclasses", "data containers"],
    ),
    (
        "python-argparse",
        "The argparse module parses command line options and arguments.",
        "Python uses argparse for command line argument parsing.",
        ["argparse", "command line"],
    ),
]


def build_demo_corpus() -> list[dict[str, Any]]:
    return [
        {
            "doc_id": doc_id,
            "text": text,
            "answer": answer,
        }
        for doc_id, text, answer, _facts in BASE_DOCS
    ]


def build_eval_cases(count: int = 500) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for index in range(count):
        doc_id, _text, answer, facts = BASE_DOCS[index % len(BASE_DOCS)]
        tag = tag_for_index(index)
        question = question_for_doc(doc_id)
        cases.append(
            {
                "external_id": f"demo-{index + 1:04d}",
                "payload": {
                    "input": {"question": question},
                    "expected_output": answer,
                    "expected_facts": facts,
                    "expected_doc_id": doc_id,
                    "forbidden_claims": ["quantum database", "telepathic compiler"],
                    "tags": sorted({"retrieval_required", tag}),
                    "difficulty": difficulty_for_tag(tag),
                },
            }
        )
    return cases


def question_for_doc(doc_id: str) -> str:
    subject = doc_id.removeprefix("python-")
    return f"Which Python module is used for {subject.replace('-', ' ')}?"


def tag_for_index(index: int) -> str:
    if index % 10 == 0:
        return "hallucination_risk"
    if index % 7 == 0:
        return "reasoning_required"
    if index % 5 == 0:
        return "edge_case"
    return "easy"


def difficulty_for_tag(tag: str) -> str:
    return "easy" if tag == "easy" else "medium"
