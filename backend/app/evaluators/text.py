import re

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def normalize_text(value: str) -> str:
    return " ".join(tokenize(value))


def tokenize(value: str) -> list[str]:
    return TOKEN_PATTERN.findall(value.lower())


def token_f1(left: str, right: str) -> float:
    left_tokens = tokenize(left)
    right_tokens = tokenize(right)
    if not left_tokens or not right_tokens:
        return 0.0

    left_set = set(left_tokens)
    right_set = set(right_tokens)
    overlap = len(left_set & right_set)
    if overlap == 0:
        return 0.0

    precision = overlap / len(left_set)
    recall = overlap / len(right_set)
    return (2 * precision * recall) / (precision + recall)
