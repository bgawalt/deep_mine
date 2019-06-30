import minesweeper

import sqlite3
import time


class DeepMine(object):

    def __init__(self, db_name, radius=2):
        self.radius = radius
        self.db_name = db_name

    def MineProbability(self, neighborhood, total_mines, flag_count):
        """Return a probability that this neighborhood's center is a mine."""
        raise NotImplentedError("MineProbability not implemented for " +
                                self.__class__.__name__)

    def PlayGame(self, ms_game, verbose=True, fps=None):
        """Play a MinesweeperGame until victory or death.  Records results."""
        neighborhoods = []
        results = []
        move = 1
        total_mines = ms_game.NumMinesTotal()
        while not ms_game.Dead() and not ms_game.Won():
            # No current support for planting flags.
            min_prob = 1
            best_spot = None
            for row in range(ms_game.num_rows):
                for col in range(ms_game.num_cols):
                    neighborhood = ms_game.Neighborhood(row, col)
                    prob = self.MineProbability(neighborhood, total_mines, 0)
                    if prob <= min_prob:
                        min_prob = prob
                        best_spot = (row, col)
            br, bc = best_spot
            neighborhoods.append(ms_game.Neighborhood(br, bc))
            result = ms_game.Dig(br, bc)
            # A result of 1 means you died.  Dig returns False if you die.
            results.append(0 if result else 1)
            if verbose:
                print("\nMove %d: (%d, %d)\n" % (move, br, bc))
                if not result:
                    print("  /!\\  DIED  /!\\ \n")
                ms_game.Print()
                print("\n")
                if fps is not None:
                    time.sleep(fps)
            move += 1
        # Save neighbs, results to sqlite
        sql_values = [(",".join([str(n) for n in neighborhood]), result)
                      for neighborhood, result in zip(neighborhoods, results)]
        conn = sqlite3.connect(self.db_name)
        curr = conn.cursor()
        # TODO: `neighborhood` takes 20% as much space if i do a crazy integer
        # format and then save as hex.  See how much data this actually
        # generates and see if that 5x shrinkage is worth the effort.
        # TODO: Encode num mines?  Board size?  Undug cell count?
        curr.execute("""
            CREATE TABLE IF NOT EXISTS digs(
                neighborhood text,
                result integer
            );""")
        curr.executemany("INSERT INTO digs VALUES (?, ?)",
            sql_values)
        conn.commit()
        conn.close()
