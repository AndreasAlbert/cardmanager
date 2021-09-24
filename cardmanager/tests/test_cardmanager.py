import os
import random
import re
import string
from unittest import TestCase

from cardmanager import CardManager


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


class TestCardManager(TestCase):
    def setUp(self):
        self.wdir = make_tmp_dir()
        self.addCleanup(os.rmdir, self.wdir)
        self.cardfile = "./tests/example_card.txt"
        self.cm = CardManager(self.cardfile, ".")

    def test_reformat(self):
        outfile = os.path.join(self.wdir, "output.txt")
        self.cm.write(outfile)
        self.addCleanup(os.remove, outfile)
        self.assertTrue(compare_cards(self.cardfile, outfile))

    def test_reformat_with_rewrite(self):
        outfile = os.path.join(self.wdir, "output.txt")
        self.cm.write(outfile)
        self.cm._rewrite_nuisance_block()
        self.addCleanup(os.remove, outfile)
        self.assertTrue(compare_cards(self.cardfile, outfile))

    def test_rewrite_with_change(self):
        outfile = os.path.join(self.wdir, "output.txt")
        self.addCleanup(os.remove, outfile)

        # Change one nuisance
        self.cm.nuisances.set_nuisance_effect("jer", "zh", "monojet_@YEAR_signal", 2)
        self.cm._rewrite_nuisance_block()
        self.cm.write(outfile)

        # Make sure output file has changed
        self.assertFalse(compare_cards(self.cardfile, outfile))

        # Manually reverse the change, create second output file
        with open(outfile, "r") as f:
            lines = f.readlines()
        new_lines = []
        for line in lines:
            if "jer" in line:
                line = line.replace("2", "1")
            new_lines.append(line)

        outfile2 = os.path.join(self.wdir, "output2.txt")
        self.addCleanup(os.remove, outfile2)
        with open(outfile2, "w") as f:
            for line in new_lines:
                f.write(line)

        # Now everything should agree again
        self.assertTrue(compare_cards(self.cardfile, outfile2))

    def test_retrieve(self):
        test_data = [
            (("jer", "zh", "monojet_@YEAR_signal"), 1),
            (("CMS_eff@YEAR_btag_udsg", "wz", "monojet_@YEAR_signal"), 1.02),
            (("CMS_eff@YEAR_btag_udsg", "top", "monojet_@YEAR_signal"), 0),
        ]
        for args, expected_value in test_data:
            self.assertEqual(
                float(self.cm.nuisances.get_nuisance_effect(*args)),
                expected_value,
                msg=f"Did not read right nuisance value for arguments: {args}",
            )
