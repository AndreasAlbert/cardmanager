from collections import defaultdict
import os
import re
from tabulate import tabulate

def line_insert(line, position, addition):
    parts = line.split()
    parts.insert(position, addition)
    return " ".join(parts)

class CardManager():
    def __init__(self, infile, wsdir):
        self.infile = infile
        self.wsdir = wsdir
        self.reset()

    def reset(self):
        '''
        Reset the in-memory version of the card to the source state.
        '''
        with open(self.infile) as f:
            self.lines = [x.strip() for x in f.readlines()]

        # Adjust the ROOT file paths
        # First, find all paths to be replaced
        rootfiles = []
        for line in self.lines:
            if not line.startswith("shapes"):
                continue
            rootfiles.append(line.split()[3])

        # Second, replace the paths
        for rf in set(rootfiles):
            abspath = os.path.join(self.wsdir, os.path.basename(rf))
            self.lines = [x.replace(" "+rf, " "+abspath) for x in self.lines]
        


    def replace_signals(self, signal_procs, srcprocs = ['vbf','ggzh','zh','wh','ggh']):
        '''
        Rewrites the card to accomodate change of signal procs.

        It is assumed that the inital card has a known set of signal processes.
        Unneeded processes are dropped (if you add fewer procs than you start out with).

        IMPORTANT: nuisances are not changed and new proces inherit the nuisances of the old proc!
        '''

        # First stop: rename initial signal processes
        # to new names given in signal_procs
        newlines = []
        for line in self.lines:
            for iproc in range(len(signal_procs)):
                # Try to preserve whitespace as well as we can
                whitespace = len(signal_procs[iproc]) - len(srcprocs[iproc])
                line = re.sub(f"{srcprocs[iproc]} {{,{whitespace}}}",signal_procs[iproc], line)
            newlines.append(line)
        self.lines = newlines

        # Mute unneeded procs
        for iproc in range(len(signal_procs), len(srcprocs)):
            self.drop_proc(srcprocs[iproc])

    def drop_unc_by_regex(self, regex):
        blocks = self.blocks()
        regex_compiled = re.compile(regex)
        blocks[4] = list(filter(lambda x: not regex_compiled.match(x.split()[0]),blocks[4]))
        self.from_blocks(blocks)

    def add_proc(self, proc, region, number, wsfile, wsstring, uncertainties={}):
        blocks = self.blocks()


        # Adjust jmax if process does not already exist
        if not any([proc==x for x in blocks[3][1].split()]):
            parts = blocks[0][2].split()
            assert(parts[0] == 'jmax')
            parts[1] = str(int(parts[1])+1)
            blocks[0][2] = " ".join(parts)

        
        # Block 1: Add shapes line
        blocks[1].append(f"shapes {proc} {region} {wsfile} {wsstring}")

        # Block 3: Add proc name, proc number, rate
        blocks[3][0] = line_insert(blocks[3][0], 1, region)
        blocks[3][1] = line_insert(blocks[3][1], 1, proc)
        blocks[3][2] = line_insert(blocks[3][2], 1, str(number))
        blocks[3][3] = line_insert(blocks[3][3], 1, "-1")

        # Block 4: Adjust uncertainties
        found_uncs = set()
        ncols = len(blocks[4][0])
        lastline = None

        # First step: Write lines for existing nuisances
        for iline, line in enumerate(blocks[4]):
            if line.split()[1] in ["lnN","shape"]:
                lastline = iline
            else:
                continue
            
            unc = line.split()[0]
            if unc in uncertainties:
                unctype, uncval = uncertainties[unc]
                assert(unctype==line.split()[1])
                uncstring = str(uncval)
                found_uncs.add(unc)
            else:
                uncstring = "-"

            blocks[4][iline] = line_insert(line, 2, uncstring)
        
        # Second step: Add new nuisance lines if necessary
        for unc in set(map(str,uncertainties.keys()))-found_uncs:
            unctype, uncval = uncertainties[unc]
            blocks[4].insert(lastline, f"{unc} {unctype} {uncval}" + (ncols-2) * " -")
            lastline += 1

        # Finally: Reassemble the lines
        self.from_blocks(blocks)

    def drop_proc(self, proc):
        '''
        Removes a process from the data card.

        Useful to e.g. drop specific signal processes.
        '''

        lines_to_drop = []
        columns_to_drop = []
        
        # Step 1: find out which columns and lines to drop
        block = 0
        for i, line in enumerate(self.lines):
            if re.match('[\-, ]*$', line):
                block += 1
                continue
            if re.match('#.*', line):
                continue
            if block == 1:
                parts = line.split()
                try:
                    assert(parts[0]=="shapes") 
                except AssertionError:
                    print("Found unexpected tag, expected 'shapes': " + parts[0] )
                iproc = parts[1]

                if iproc==proc or re.match(proc, iproc):
                    lines_to_drop.append(i)
            elif block == 3:
                if not line.startswith("process"):
                    continue
                parts = line.split()
                for ipart, part in enumerate(parts):
                    if part == proc or re.match(proc, part):
                        columns_to_drop.append(ipart)

        # Step 2: drop the lines
        for i in reversed(sorted(list(set(lines_to_drop)))):
            self.lines.pop(i)
        
        # Step 3: drop the columns:
        block = 0
        lines = []
        for i, line in enumerate(self.lines):
            if re.match('[\-, ]*$', line):
                block += 1
                lines.append(line)
                continue
            if block in [3,4]:
                parts = line.split()
                if parts[0] not in ['bin','process','rate'] and parts[1] not in ['shape','lnN']:
                    lines.append(line)
                    continue
                for icol in reversed(sorted(list(set(columns_to_drop)))):
                    parts.pop(icol if block==3 else icol+1)
                line = " ".join(parts)
            lines.append(line)

        # Adjust number of processes
        parts = lines[2].split()
        assert(parts[0] == 'jmax')
        parts[1] = str(int(parts[1])-1)
        lines[2] = " ".join(parts)
        self.lines = lines
    
    def sub(self, pattern, substitute):
        self.lines = [re.sub(pattern, substitute, line) for line in self.lines]

    def add_line(self, line, block=-1):
        '''Adds a line to the end of the card.'''
        blocks = self.blocks()
        blocks[block].append(line)
        self.from_blocks(blocks)

    def from_blocks(self, blocks):
        lines = []
        for tmp in blocks:
            lines.extend(tmp)
            lines.append('-'*20)
        self.lines = lines

    def blocks(self):
        '''Format lines into blocks'''
        block = 0
        blocks = []
        for i, line in enumerate(self.lines):
            if re.match('[\-, ]*$', line):
                block += 1
                continue
            if block < len(blocks):
                blocks[block].append(line)
            else:
                blocks.append([line])
        return blocks

    def write(self, outfile):
        '''Writes the data card to a text file.'''
        # For formatting, disassemble the card into blocks
        blocks = self.blocks()

        # Re-assemble the blocks
        separator = "-" * 20

        # Remove nuisance number
        parts = blocks[0][3].split()
        assert(parts[0] == 'kmax')
        parts[1] = "*"
        blocks[0][3] = " ".join(parts)

        with open(outfile, "w") as f:
            # Block 0 does not formatting
            f.write("\n".join(blocks[0])+"\n")
            f.write(separator + "\n")

            # Blocks 1 and 2 are table-formatted independently
            for i in [1,2]:
                f.write(tabulate([x.split() for x in blocks[i]], tablefmt='plain')+"\n")
                f.write(separator + "\n")

            # Blocks 3 and 4 are table formatted together
            # Block 4 has the additional nuisance type identifier (e.g. "lnN"),
            # so we add a dummy entry in block 3 to preserve column formatting
            for i in range(len(blocks[3])):
                parts = blocks[3][i].split()
                parts.insert(1,'DUMMY')
                blocks[3][i] = " ".join(parts)
            
            # Apply table formatting to merged 3+4
            tmp = tabulate([x.split() for x in blocks[3]+blocks[4]], tablefmt='plain').split('\n')

            # Insert separator
            tmp.insert(4, separator)

            # Remove dummy column entry and write
            f.write("\n".join(tmp).replace("DUMMY","     ")+"\n")

            # # Block 5 does not get special formatting
            # f.write("\n".join(blocks[5])+"\n")


