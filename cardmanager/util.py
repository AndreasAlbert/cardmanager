import os
import random
import re
import string


def sub_line(line: str) -> str:
    line = re.sub(" +", " ", line)
    line = re.sub("-+", "-", line)
    line = line.strip()
    return line


def load_card_for_comparison(card_file: str) -> "list[str]":
    with open(card_file, "r") as f:
        lines = f.readlines()

    return list(map(sub_line, lines))


def compare_items(item1: str, item2: str) -> bool:
    """
    Evaluate whether two items of split data card lines are effectively equivalent ignoring formatting.
    """
    if item1 == item2:
        return True
    try:
        item1_as_float = float(item1)
        item2_as_float = float(item2)
        if item1_as_float == item2_as_float:
            return True
    except ValueError:
        pass
    return False


def compare_lines(line1: str, line2: str) -> bool:
    """
    Evaluate whether two data card lines are effectively equivalent ignoring formatting.
    """
    if line1 == line2:
        return True
    return all(
        [
            compare_items(item1, item2)
            for item1, item2 in zip(line1.split(), line2.split())
        ]
    )


def compare_cards(card1: str, card2: str) -> bool:
    """
    Evaluate whether two data cards are effectively equivalent ignoring formatting.
    """
    lines_card1 = load_card_for_comparison(card1)
    lines_card2 = load_card_for_comparison(card2)

    return all(
        [compare_lines(line1, line2) for line1, line2 in zip(lines_card1, lines_card2)]
    )


def random_id(length=16):
    """Random string ID for naming temporary files etc"""
    return "".join(random.choices(string.ascii_lowercase, k=length))


def make_tmp_dir():
    """Creation of randomly named working directories for tests"""
    wdir = "/tmp/tmp_" + random_id(32)
    if os.path.exists(wdir):
        return make_tmp_dir()
    os.makedirs(wdir)
    return wdir
