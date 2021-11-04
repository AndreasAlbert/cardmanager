import os
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass

from tabulate import tabulate


def line_insert(line, position, addition):
    parts = line.split()
    parts.insert(position, addition)
    return " ".join(parts)


@dataclass
class Process:
    id: int
    name: str

    def __eq__(self, other):
        return self.id == other.id and self.name == other.name

    def __hash__(self):
        return hash(self.id)


@dataclass
class Nuisance:
    """
    Class that represents a single nuisance parameter.

    Nuisance values are stored in a dictionary.

    key = (process_name, region_name)
    value = string data card entry
    """

    name: str
    type: str

    effects: "dict[(str,str) : str]"

    def get_nuisance_effect(self, process_name: str, region_name: str) -> str:
        try:
            return self.effects[(process_name, region_name)]
        except KeyError:
            return "-"

    def set_nuisance_effect(
        self, process_name: str, region_name: str, effect: float
    ) -> None:
        self.effects[(process_name, region_name)] = effect

    def affects_process(self, process_name, region_name=None):
        if region_name is None:
            return any([process_name in key for key in self.effects.keys()])
        else:
            return (process_name, region_name) in self.effects


@dataclass
class NuisanceCollection:
    nuisances: "dict[str:Nuisance]"

    def get_nuisance_effect(
        self, nuisance_name: str, process_name: str, region_name: str
    ) -> float:
        return self.nuisances[nuisance_name].get_nuisance_effect(
            process_name, region_name
        )

    def set_nuisance_effect(
        self, nuisance_name: str, process_name: str, region_name: str, effect: float
    ) -> float:
        return self.nuisances[nuisance_name].set_nuisance_effect(
            process_name, region_name, effect
        )

    def add_nuisance(self, nuisance: Nuisance) -> None:
        if nuisance.name in self.nuisances:
            raise KeyError(f"Cannot insert duplicate nuisance name: {nuisance.name}")
        self.nuisances[nuisance.name] = nuisance

    def remove_nuisance(self, nuisance_name: str) -> Nuisance:
        if not nuisance_name in self.nuisances:
            raise KeyError(f"Cannot remove nonexisting nuisance name: {nuisance.name}")
        return self.nuisances.pop(nuisance_name)

    def __getitem__(self, key: str) -> Nuisance:
        return self.nuisances[key]

    def keys(self):
        return self.nuisances.keys()


@dataclass
class CardFormat:
    """
    This class handles all operations related to the specific layout
    of combine data cards. Each card follows the following format
    of consecutive blocks of lines:

    0 - header block    (contains imax, jmax, kmax, possible annotations)
    ---- separator       (line consisting exclusively of hyphens)
    1 - shape block      (contains definitions of shape histograms)
    ---- separator
    2 - bin block       (contains definitions of bins)
    ---- separator
    3 - process block   (Definition of what processes are present in what regions)
    ---- separator
    4 - nuisance block  (Definition of which nuisance affects what process where)
    5 - param block     (Definition of additional parameters, rename statements, etc)
    """

    def __post_init__(self):
        self.block_names = ["header", "shape", "bin", "process", "nuisance", "param"]

    def block_counter_to_name(self, block_counter: int) -> str:
        return self.block_names[block_counter]

    def _is_separator_line(self, line: str) -> bool:
        return bool(re.match("[-, ]*$", line))

    def _find_separator_lines(self, lines) -> "list[int]":
        return [
            index for index, line in enumerate(lines) if self._is_separator_line(line)
        ]

    def _find_first_line_of_param_block(self, lines: "list[str]") -> int:
        previous_line_length = 0
        for index, line in enumerate(lines):
            line_length = len(line.split())
            if previous_line_length > line_length:
                return index
            previous_line_length = line_length
        raise RuntimeError(
            "Could not find separation between nuisance and param blocks!"
        )

    def _remap_keys_counter_to_name(
        self, blocks: "dict[str:list[list[str]]]"
    ) -> "dict[str:list[list[str]]]":
        return {self.block_counter_to_name(key): value for key, value in blocks.items()}

    def _split_lines_by_separators(self, lines: "list[str]") -> "list[list[str]]":
        """
        Subdivides a list of lines into raw blocks based on separator line locations.

        The separator lines are dropped in the process.
        """
        separator_line_indices = self._find_separator_lines(lines)

        blocks = []
        for block_counter in range(len(separator_line_indices) + 1):
            line_index_start = 0
            if block_counter > 0:
                line_index_start = separator_line_indices[block_counter - 1] + 1
            if block_counter >= len(separator_line_indices):
                line_index_stop = len(lines)
            else:
                line_index_stop = separator_line_indices[block_counter]

            block = lines[line_index_start:line_index_stop]
            blocks.append(block)
        return blocks

    def lines_to_blocks(
        self, lines: "list[str]", key_is_name=False
    ) -> "dict[str:list[list[str]]":
        """
        Format data card lines into blocks.

        The lines should contain all lines from the data card, including all blocks
        and separators.

        Separator lines will be dropped, and will not show up in the blocks.

        Results are returned as a dictionary, where the key is either the
        block index or the block name (if key_is_name is provided). For each
        key, the value is a list of lines (strings).
        """

        blocks = {}

        # Every card should have five sets of lines split by separators
        raw_blocks = self._split_lines_by_separators(lines)
        assert len(raw_blocks) == 5

        # The first four of those five are the blocks we care about
        for block_counter in range(4):
            blocks[block_counter] = raw_blocks[block_counter]

        # The fifth set of lines contains the blocks five and six,
        # which are not separated by a separator line in the format.
        # Leftover lines are scanned to dynamically find the boundary
        # and then split accordingly.
        first_line_of_param_block = self._find_first_line_of_param_block(raw_blocks[-1])

        block_counter += 1
        blocks[block_counter] = raw_blocks[-1][:first_line_of_param_block]

        block_counter += 1
        blocks[block_counter] = raw_blocks[-1][first_line_of_param_block:]

        # Make sure we did not lose any lines
        n_lines_raw = len(raw_blocks[-1])
        n_lines_processed = len(blocks[block_counter]) + len(blocks[block_counter - 1])
        assert n_lines_raw == n_lines_processed

        # If desired, output dictionary has block names
        # instead of int keys
        if key_is_name:
            blocks = self._remap_keys_counter_to_name(blocks)

        return dict(blocks)

    def _generate_separator(self) -> str:
        return "-" * 20

    def _tabulate(self, lines: "list[str]") -> str:
        text = tabulate([line.split() for line in lines], tablefmt="plain")
        return text

    def format_lines_header_block(
        self, blocks: "list[list[str]]", separators: bool = True
    ) -> "list[str]":
        lines = blocks["header"]
        if separators:
            lines.append(self._generate_separator())
        return lines

    def format_lines_shape_bin_blocks(
        self, blocks: "list[list[str]]", separators: bool = True
    ) -> "list[str]":
        lines = []
        # Blocks 1 and 2 are table-formatted independently
        for block_name in ["shape", "bin"]:
            table = self._tabulate(blocks[block_name])
            lines.extend(table.splitlines())
            if separators:
                lines.append(self._generate_separator())
        return lines

    def format_lines_process_nuisance_blocks(
        self, blocks: "list[list[str]]", separators: bool = True
    ) -> "list[str]":
        process_block = blocks["process"].copy()
        nuisance_block = blocks["nuisance"].copy()
        for i in range(len(process_block)):
            parts = process_block[i].split()
            parts.insert(1, "DUMMY")
            process_block[i] = " ".join(parts)

        merged_block = process_block + nuisance_block
        text = self._tabulate(merged_block)
        text = text.replace("DUMMY", "     ")
        lines = text.splitlines()
        if separators:
            lines.insert(len(process_block), self._generate_separator())
        return lines

    def format_lines_param_block(self, blocks: "list[list[str]]") -> "list[str]":
        return self._tabulate(blocks["param"]).splitlines()

    def blocks_to_lines(
        self, blocks, separators: bool = True, index_is_name: bool = True
    ) -> "list[str]":
        # Re-assemble the blocks
        if not index_is_name:
            blocks = self._remap_keys_counter_to_name(blocks)

        lines = self.format_lines_header_block(blocks, separators)
        lines.extend(self.format_lines_shape_bin_blocks(blocks, separators))
        lines.extend(self.format_lines_process_nuisance_blocks(blocks, separators))
        lines.extend(self.format_lines_param_block(blocks))
        return lines


class CardManager:
    def __init__(self, infile):
        self.infile = infile
        self.processes = []
        self.blocks = []
        self.nuisances = NuisanceCollection([])
        self.format = CardFormat()
        self.reset()

    def _read_lines_from_file(self, filepath: str) -> None:
        with open(filepath) as f:
            lines = [x.strip() for x in f.readlines()]
        return lines

    def _update_blocks_from_lines(self, lines):
        self.blocks = self.format.lines_to_blocks(lines, key_is_name=True)

    def get_lines(self, separators=True):
        return self.format.blocks_to_lines(self.blocks, separators)

    def reset(self):
        """
        Reset the in-memory version of the card to the source state.
        """
        lines = self._read_lines_from_file(self.infile)
        self._update_blocks_from_lines(lines)
        self.processes = self._parse_processes_in_card()
        self.nuisances = NuisanceCollection(self._parse_nuisances_in_card())

    def _parse_processes_in_card(self) -> "list[Process]":
        """Get list of unique existing processes"""
        process_name_list = self.blocks["process"][1]
        process_id_list = self.blocks["process"][2]

        processes = []
        for name, id in zip(process_name_list, process_id_list):
            processes.append(Process(id=id, name=name))
        return list(set(processes))

    def _process_region_pairs(self):
        pairs = list(
            zip(
                self.blocks["process"][1].split()[1:],
                self.blocks["process"][0].split()[1:],
            )
        )

        return pairs

    def _parse_nuisances_in_card(self):
        """
        Creates Nuisance objects from the nuisance block information.

        The nuisance block
        """

        bins = self.blocks["process"][0].split()[1:]
        process_names = self.blocks["process"][1].split()[1:]

        nuisances = {}
        for nuisance_line in self.blocks["nuisance"]:
            line_entries = nuisance_line.split()

            nuisance_name = line_entries[0]
            nuisance_type = line_entries[1]
            nuisance_values = line_entries[2:]

            nuisance_values = [0 if x == "-" else x for x in nuisance_values]

            nuisance_effects = {
                (process_name, bin_name): nuisance_value
                for process_name, bin_name, nuisance_value in zip(
                    process_names, bins, nuisance_values
                )
            }

            nuisance = Nuisance(
                name=nuisance_name, type=nuisance_type, effects=nuisance_effects
            )
            nuisances[nuisance_name] = nuisance
        return nuisances

    def _rewrite_nuisance_block(self):
        new_block = []
        for nuisance in self.nuisances.nuisances.values():
            split_line = [nuisance.name, nuisance.type]
            for process, region in self._process_region_pairs():
                effect = nuisance.get_nuisance_effect(process, region)
                split_line.append("-" if effect == 0 else effect)
            new_block.append(" ".join(map(str, split_line)))
        self.blocks["nuisance"] = new_block

    def get_workspace_file_paths(self, blocks=None):
        if not blocks:
            blocks = self.blocks

        file_paths = set()
        for line in blocks["shape"]:
            for entry in line.split():
                entry = re.sub(":.*", "", entry)
                if not entry.endswith(".root"):
                    continue
                file_paths.add(entry)
        return list(file_paths)

    def make_file_paths_basic(self, blocks=None, inplace: bool = False) -> dict:
        """
        Modify references to workspace files inside the card to naming just the file base name.

        Example: Replace "/path/to/file.root" with "file.root".
        """
        if not blocks:
            blocks = self.blocks

        for file_path in self.get_workspace_file_paths(blocks):
            for iline, line in enumerate(blocks["shape"]):
                blocks["shape"][iline] = line.replace(
                    file_path, os.path.basename(file_path)
                )

        if inplace:
            self.blocks = blocks

        return blocks

    def copy_workspace_files(self, blocks: dict, target_directory: str) -> None:
        """
        Copies the workspace files referenced in the data card blocks to the target directory.
        """
        source_paths = self.get_workspace_file_paths(blocks)

        base_names_seen = set()
        for ipath in source_paths:
            base_name = os.path.basename(ipath)
            assert (
                not base_name in base_names_seen
            ), f"Clash of workspace base names: {base_name}"
            base_names_seen.add(base_name)
            target_path = os.path.join(target_directory, base_name)
            shutil.copyfile(ipath, target_path)

    def write(self, outfile, copy_workspaces=False):
        """Writes the data card to a text file."""
        blocks = self.blocks.copy()

        outdir = os.path.dirname(outfile)
        if copy_workspaces:
            self.copy_workspace_files(blocks, outdir)
            blocks = self.make_file_paths_basic(blocks)

        formatted_lines = self.format.blocks_to_lines(blocks, separators=True)

        try:
            os.makedirs(outdir)
        except FileExistsError:
            pass

        with open(outfile, "w") as f:
            f.write("\n".join(formatted_lines))

    def make_file_paths_absolute(self, blocks=None, inplace=False) -> None:
        """
        Modify references to workspace files inside the card to make them absolute paths.
        """

        if not blocks:
            blocks = self.blocks

        parent = os.path.dirname(self.infile)

        def make_abs_if_file(string: str) -> str:
            if string.endswith(".root"):
                if string.startswith("/"):
                    return string
                return os.path.abspath(os.path.join(parent, string))
            return string

        for iline, line in enumerate(blocks["shape"]):
            blocks["shape"][iline] = " ".join(
                [make_abs_if_file(x) for x in line.split()]
            )

        if inplace:
            self.blocks = blocks

        return blocks
