import os
from unittest import TestCase

from cardmanager.util import make_tmp_dir, compare_cards
from cardmanager import CardManager


class TestCardManager(TestCase):
    def setUp(self):
        self.wdir = make_tmp_dir()
        self.addCleanup(os.rmdir, self.wdir)
        self.cardfile = "./cardmanager/tests/example_card.txt"
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
