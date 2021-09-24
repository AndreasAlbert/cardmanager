from collections import defaultdict
from dataclasses import dataclass
import os
import re
from tabulate import tabulate

def line_insert(line, position, addition):
    parts = line.split()
    parts.insert(position, addition)
    return " ".join(parts)

@dataclass
class Process():
    id: int
    name: str

    def __eq__(self, other):
        return self.id==other.id and self.name==other.name

    def __hash__(self):
        return hash(self.id)

@dataclass
class Nuisance():
    name: str
    type: str

    effects: 'dict[str : float]'

    def get_nuisance_effect(self,process_name: str, region_name: str)->float:
        return self.effects[(process_name, region_name)]

    def affects_process(self, process_name, region_name=None):
        if region_name is None:
            return any([process_name in key for key in self.effects.keys()])
        else:
            return (process_name, region_name) in self.effects
    

@dataclass 
class NuisanceCollection():
    nuisances : 'dict[str:Nuisance]'

    def get_nuisance_effect(nuisance_name : str, process_name : str, region_name: str) -> float:
        self.nuisances[nuisance_name].get_nuisance_effect(process_name, region_name)
    
    def add_nuisance(self,nuisance:Nuisance) -> None:
        if nuisance.name in self.nuisances:
            raise KeyError(f"Cannot insert duplicate nuisance name: {nuisance.name}")
        self.nuisances[nuisance.name] = nuisance

    def __getitem__(self,key:str)->Nuisance:
        return self.nuisances[key]

    def keys(self):
        return self.nuisances.keys()


@dataclass
class CardFormat():
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
        self.block_names = ['header', 'shape', 'bin', 'process', 'nuisance', 'param']

    def block_counter_to_name(self,block_counter:int)->str:
        return self.block_names[block_counter]

    def _is_separator_line(self, line: str)->bool:
        return  bool(re.match('[\-, ]*$', line))

    def _find_separator_lines(self, lines)->'list[int]':
        return [index for index, line in enumerate(lines) if self._is_separator_line(line)]

    def _find_first_line_of_param_block(self, lines: 'list[str]')->int:
        previous_line_length = 0
        for index, line in enumerate(lines):
            line_length = len(line.split())
            if previous_line_length > line_length:
                return index
            previous_line_length = line_length
        raise RuntimeError("Could not find separation between nuisance and param blocks!")

    def _remap_keys_counter_to_name(self, blocks):
        return {self.block_counter_to_name(key): value for key, value in blocks.items()}

    def _split_lines_by_separators(self, lines):
        separator_line_indices = self._find_separator_lines(lines)
        
        blocks = []
        for block_counter in range(len(separator_line_indices)+1):
            
            line_index_start = 0
            if block_counter>0:
                line_index_start = separator_line_indices[block_counter-1] + 1
            line_index_stop = separator_line_indices[block_counter]

            block = lines[line_index_start:line_index_stop]
            blocks.append(block)


    def lines_to_blocks(self,lines:'list[str]', key_is_name=False) -> 'dict':
        '''
        Format data card lines into blocks.

        The lines should contain all lines from the data card, including all blocks
        and separators.

        Separator lines will be dropped, and will not show up in the blocks.

        Results are returned as a dictionary, where the key is either the 
        block index or the block name (if key_is_name is provided). For each
        key, the value is a list of lines (strings).
        '''

        blocks = {}

        # A card should always contain exactly four separator lines
        separator_line_indices = self._find_separator_lines(lines)
        assert(len(separator_line_indices) == 4)

        # The first four blocks are all separated by separators
        # so we split exactly at the separator, and drop the separator lines
        for block_counter in range(0,4):
            line_index_start = 0
            if block_counter>0:
                line_index_start = separator_line_indices[block_counter-1] + 1
            line_index_stop = separator_line_indices[block_counter]

            blocks[block_counter] = lines[line_index_start:line_index_stop]

        # Blocks five and six are not separated by a separator
        # Leftover lines are scanned to dynamically find theb boundary
        # and then split accordingly.
        last_separator_index = separator_line_indices[-1]
        leftover_lines = lines[last_separator_index+1:]


        first_line_of_param = self._find_first_line_of_param_block(leftover_lines)

        block_counter += 1
        blocks[block_counter] = leftover_lines[:first_line_of_param]

        block_counter += 1
        blocks[block_counter] = leftover_lines[first_line_of_param:]

        if key_is_name:
            blocks = self._remap_keys_counter_to_name(blocks)

        return dict(blocks)

    def _generate_separator(self):
        return "-" * 20

    def _tabulate(self,lines):
        text = tabulate([line.split() for line in lines], tablefmt='plain')
        return text

    def format_lines_header_block(self, blocks, separators=True):
        lines = blocks['header']
        if separators:
            lines.append(self._generate_separator())
        return lines

    def format_lines_shape_bin_blocks(self, blocks, separators=True):
        lines = []
        # Blocks 1 and 2 are table-formatted independently
        for block_name in ['shape', 'bin']:
            table = self._tabulate(blocks[block_name])
            lines.extend(table.splitlines())
            if separators:
                lines.append(self._generate_separator())
        return lines
    
    def format_lines_process_nuisance_blocks(self, blocks, separators=True):

        # Blocks 3 and 4 are table formatted together
        # Block 4 has the additional nuisance type identifier (e.g. "lnN"),
        # so we add a dummy entry in block 3 to preserve column formatting

        process_block = blocks['process']
        nuisance_block = blocks['nuisance']
        for i in range(len(process_block)):
            parts = process_block[i].split()
            parts.insert(1,'DUMMY')
            process_block[i] = " ".join(parts)

        merged_block = process_block + nuisance_block
        text = self._tabulate(merged_block)
        text = text.replace("DUMMY","     ")
        lines = text.splitlines()

        if separators:
            lines.insert(len(process_block), self._generate_separator())
            lines.append(self._generate_separator())
        return lines

    def format_lines_param_block(self, blocks):
        return self._tabulate(blocks['param']).splitlines()

    def blocks_to_lines(self, blocks, separators=True, index_is_name=True):
        # Re-assemble the blocks
        if not index_is_name:
            blocks = self._remap_keys_counter_to_name(blocks)

        lines = self.format_lines_header_block(blocks, separators)
        lines.extend(self.format_lines_shape_bin_blocks(blocks, separators))
        lines.extend(self.format_lines_process_nuisance_blocks(blocks, separators))
        lines.extend(self.format_lines_param_block(blocks))
        return lines

class CardManager():
    def __init__(self, infile, wsdir):
        self.infile = infile
        self.wsdir = wsdir
        self.processes = []
        self.blocks = []
        self.nuisances = NuisanceCollection([])
        self.format = CardFormat()
        self.reset()

    def _read_lines_from_file(self, filepath:str)->None:
        with open(filepath) as f:
            lines = [x.strip() for x in f.readlines()]
        return lines

    def _update_blocks_from_lines(self, lines):
        self.blocks = self.format.lines_to_blocks(lines, key_is_name=True)

    def get_lines(self, separators=True):
        return self.format.blocks_to_lines(self.blocks, separators)

    def reset(self):
        '''
        Reset the in-memory version of the card to the source state.
        '''
        lines = self._read_lines_from_file(self.infile)
        self._update_blocks_from_lines(lines)
        self.processes = self._parse_processes_in_card()
        self.nuisances = NuisanceCollection(self._parse_nuisances_in_card())

    def _parse_processes_in_card(self) -> 'list[Process]':
        """Get list of unique existing processes"""
        process_name_list = self.blocks['process'][1]
        process_id_list = self.blocks['process'][2]

        processes = []
        for name, id in zip(process_name_list, process_id_list):
            processes.append(Process(id=id, name=name))
        return list(set(processes))

    def _process_region_pairs(self):
        pairs = list(zip(
            self.blocks['process'][1].split()[1:],
            self.blocks['process'][0].split()[1:]
        ))

        return pairs

    def from_blocks(self, blocks):
        lines = []
        for tmp in blocks:
            lines.extend(tmp)
            lines.append('-'*20)
        self.lines = lines
        self._update_blocks()

    def _parse_nuisances_in_card(self):
        """
        Creates Nuisance objects from the nuisance block information.

        The nuisance block 
        """

        bins = self.blocks['process'][0].split()[1:]
        process_names = self.blocks['process'][1].split()[1:]

        nuisances = {}
        for nuisance_line in  self.blocks['nuisance']:
            line_entries = nuisance_line.split()

            nuisance_name = line_entries[0]
            nuisance_type = line_entries[1]
            nuisance_values = line_entries[2:]

            nuisance_effects = {(process_name, bin_name) : nuisance_value for process_name, bin_name, nuisance_value in zip(nuisance_values, bins, process_names)}

            nuisance = Nuisance(
                name=nuisance_name,
                type=nuisance_type,
                effects=nuisance_effects
            )
            nuisances[nuisance_name] = nuisance
        return nuisances
    
    def _rewrite_nuisance_block(self):
        new_block = []
        for nuisance in self.nuisances:
            split_line = [nuisance.name, nuisance.type]
            for process, region in self._processes_pairs():
                split_line.append(nuisance.get_effect(process, region))
            new_block.append(new_block)
        self.blocks['nuisance'] = new_block

        self.from_blocks(blocks)

    def write(self, outfile):
        '''Writes the data card to a text file.'''
        formatted_lines = self.format.blocks_to_lines(self.blocks, separators=True)
        with open(outfile, "w") as f:
            f.write("\n".join(formatted_lines))
