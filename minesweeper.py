"""Library defining Minesweeper game, with main() letting you play it.

To play a game, optionally add 'm' or 'h' to your command line arguments:

$ python minesweeper.py {m | h}

That will let you play a _m_edium or _h_ard board (and will otherwise have you
play an easy board).

TODO: Upgrade style to use snake_case for functions/methods.
"""

import enum
import sys
import random

@enum.unique
class CellValue(enum.Enum):
    """Non-numeric values that can be held by a game cell."""
    UNKNOWN = (".", "🟩", -1)
    FLAG = ("F", "🚩", -2)
    OUT_OF_BOUNDS = ("x", "x", -3)
    MINE = ("#", "💣", -4)
    LAVA = ("~", "🔥", -5)

    def __int__(self):
        return self.value[2]

_NUMERIC_EMOJI = tuple(["🟫", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"])
_TWEET_ROW_INDICES = tuple(chr(0x1f1e6 + i) for i in range(8))
_TWEET_COL_HEADER = (
    "🟦" +
    "".join(chr(u) for u in
            (0x1f1ee, 0x1f1ef, 0x1f1f0, 0x1f1f1,
             0x1f1f3, 0x1f1f6, 0x1f1f7, 0x1f1f9)) + "\n")

def _DisplayCell(cell_value, use_emoji=False):
    """Single character to display for the given cell_value."""
    if isinstance(cell_value, CellValue):
        return cell_value.value[1 if use_emoji else 0]
    if use_emoji:
        return _NUMERIC_EMOJI[cell_value]
    return ' ' if cell_value == 0 else str(cell_value)


class MinesweeperGame(object):

    def __init__(self, num_rows, num_cols, num_mines, seed=None):
        if num_rows < 1:
            raise ValueError("num_rows must be positive")
        if num_cols < 1:
            raise ValueError("num_cols must be positive")
        if num_mines < 0:
            raise ValueError("num_mines must be non-negative")
        self.num_rows = num_rows
        self.num_cols = num_cols
        self.dead = False
        # Choose random mine positions
        random.seed(seed)
        self.mine_positions = set(
            random.sample([(row, col) for row in range(num_rows)
                           for col in range(num_cols)],
                          num_mines))
        # Precompute number of neighboring mines for each square
        # Start by every square thinking it has zero neighbors:
        self.num_neighbors = {(row, col): 0
                              for row in range(num_rows)
                              for col in range(num_cols)}
        # Then, for every mine, increment its neighbors' counts:
        for mine_position in self.mine_positions:
            mrow, mcol = mine_position
            for drow in (mrow - 1, mrow, mrow + 1):
                for dcol in (mcol - 1, mcol, mcol + 1):
                    if self.ValidPosition(drow, dcol):
                        self.num_neighbors[(drow, dcol)] += 1
        self.board = {(row, col): CellValue.UNKNOWN
                      for row in range(num_rows)
                      for col in range(num_cols)}
        self.dug_count = 0
        self.flag_count = 0
        # Keep track of cells dug up or flagged since the last visualization:
        self.recently_poked = []

    @staticmethod
    def Beginner(seed=None):
        return MinesweeperGame(8, 8, 10, seed)

    @staticmethod
    def Intermediate(seed=None):
        return MinesweeperGame(16, 16, 40, seed)

    @staticmethod
    def Expert(seed=None):
        return MinesweeperGame(24, 24, 99, seed)

    def ValidPosition(self, row, col):
        return 0 <= row < self.num_rows and 0 <= col < self.num_cols

    def PlantFlag(self, row, col):
        if not self.ValidPosition(row, col):
            raise ValueError("Can't plant a flag outside the board")
        self.board[(row, col)] = CellValue.FLAG
        self.flag_count += 1
        self.recently_poked.append(row, col)

    def Dig(self, row, col):
        """Returns True iff you dig a *new* hole and survive."""
        if self.dead:
            raise ValueError("What's dead can never dig")
        if not self.ValidPosition(row, col):
            # sure.  just dig wherever.  no mines outside the board anyway.
            return True
        if (row, col) in self.mine_positions:
            self.board[(row, col)] = CellValue.MINE
            self.dead = True
            return False
        if self.board[(row, col)] != CellValue.UNKNOWN:
            self.board[(row, col)] = CellValue.LAVA
            self.dead = True
            return False
        neighbors = self.num_neighbors[(row, col)]
        self.board[(row, col)] = neighbors
        # If no neighboring cells are mines, dig up all those cells, too:
        if neighbors == 0:
            # Explore all neighbors
            seen = set()
            to_dig = []
            for drow in (row - 1, row, row + 1):
                for dcol in (col - 1, col, col + 1):
                    if not self.ValidPosition(drow, dcol):
                        continue
                    if self.board[(drow, dcol)] == CellValue.UNKNOWN:
                        to_dig.append((drow, dcol))
            while len(to_dig) > 0:
                nrow, ncol = to_dig.pop()
                if (nrow, ncol) in seen:
                    continue
                seen.add((nrow, ncol))
                nneigh = self.num_neighbors[(nrow, ncol)]
                self.board[(nrow, ncol)] = nneigh
                self.dug_count += 1
                if nneigh == 0:
                    for drow in (nrow - 1, nrow, nrow + 1):
                        for dcol in (ncol - 1, ncol, ncol + 1):
                            if not self.ValidPosition(drow, dcol):
                                continue
                            if self.board[(drow, dcol)] == CellValue.UNKNOWN:
                                to_dig.append((drow, dcol))
        self.dug_count += 1
        self.recently_poked.append((row, col))
        if self.Won():
            for mrow, mcol in self.mine_positions:
                self.board[(mrow, mcol)] = CellValue.FLAG
        return True

    def Neighborhood(self, row, col, radius=2):
        """Row-major ordering of what the board looks like centered at (r, c)"""
        # Returns list of ints representing cell values.
        vals = []
        for drow in range(row - radius, row + radius + 1):
            for dcol in range(col - radius, col + radius + 1):
                if self.ValidPosition(drow, dcol):
                    vals.append(int(self.board[(drow, dcol)]))
                else:
                    vals.append(int(CellValue.OUT_OF_BOUNDS))
        return vals

    def NumUnflagged(self):
        return len(self.mine_positions) - self.flag_count

    def NumMinesTotal(self):
        return len(self.mine_positions)

    def Dead(self):
        return self.dead

    def Won(self):
        # WARNING!! IGNORES FLAGS!!
        return (len(self.board) - self.dug_count) == self.NumMinesTotal()

    def Print(self, include_ticks=False):
        print(f"Dig Count: {self.dug_count}")
        print(f"Mines: {self.NumMinesTotal()}\n")
        # Print a row of ticks above the board:
        if include_ticks:
            print(" " * (len(str(self.num_rows)) + 2), end='')
            col = 0
            out_str = ""
            while col < self.num_cols:
                if col % 3 == 0:
                    addition = str(col)
                    if len(addition) == 1:
                        addition += ' '
                else:
                    addition = '  '
                out_str += addition
                col += 1
            print(out_str, end='\n')
        for row in range(self.num_rows):
            # Print a single tick to the left of the board:
            if include_ticks:
                n = len(str(self.num_rows))
                print(("%d" % (row,)).rjust(n), end='  ')
            for col in range(self.num_cols):
                cell_value = self.board[(row, col)]
                ch = _DisplayCell(cell_value)
                print(ch, end=' ')
            print('')
        # Print a row of ticks below the board:
        if include_ticks:
            print(" " * (len(str(self.num_rows)) + 2), end='')
            col = 0
            out_str = ""
            while col < self.num_cols:
                if col % 3 == 0:
                    addition = str(col)
                    if len(addition) == 1:
                        addition += ' '
                else:
                    addition = '  '
                out_str += addition
                col += 1
            print(out_str, end='\n')
        self.recently_poked = []

    def AsEmoji(self):
        """Returns a game board rendered as emoji."""
        tweet_board = _TWEET_COL_HEADER
        for row_id in range(self.num_rows):
            row = [_DisplayCell(self.board[(row_id, col_id)], use_emoji=True)
                   for col_id in range(self.num_cols)]
            tweet_board += (_TWEET_ROW_INDICES[row_id] + "".join(row) + "\n")
        return tweet_board


if __name__ == "__main__":
    # Demo usage:
    if 'm' in sys.argv:
        ms_game = MinesweeperGame.Intermediate()
    elif 'h' in sys.argv:
        ms_game = MinesweeperGame.Expert()
    else:
        ms_game = MinesweeperGame.Beginner()

    print("Welcome to minesweeper!", end="\n\n")
    moves = 1
    ms_game.Print(include_ticks=True)
    print(ms_game.AsEmoji())
    print("\n")
    while not ms_game.Dead() and not ms_game.Won():
        row = int(input("Row: "))
        col = int(input("Col: "))
        print(f"Move {moves}: [{row}, {col}]:", end=" ")
        print(ms_game.num_neighbors[(row, col)])
        if not ms_game.Dig(row, col):
            print("   DIED!!\n")
        else:
            print('  (... whew...)\n')
        ms_game.Print(include_ticks=True)
        print(ms_game.AsEmoji())
        print("\n\n")
        moves += 1
    if ms_game.Won():
        print("YOU WIN!!!")
