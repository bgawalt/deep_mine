import minesweeper

import random
import sqlite3

from scipy import sparse


class DeepMine(object):

    def __init__(self, db_name, radius=2):
        self.radius = radius
        self.db_name = db_name

    def MineProbability(self, neighborhood, total_mines, flag_count):
        """Return a probability that this neighborhood's center is a mine."""
        raise NotImplentedError("MineProbability not implemented for " +
                                self.__class__.__name__)

    def PlayGame(self, ms_game):
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
            print("\nMove %d: (%d, %d)\n" % (move, br, bc))
            if not result:
                print("  /!\\  DIED  /!\\ \n")
            ms_game.Print()
            print("\n")
            move += 1
        # Save neighbs, results to sqlite
        sql_values = [(",".join([str(n) for n in neighborhood]), result)
                      for neighborhood, result in zip(neighborhoods, results)]
        conn = sqlite3.connect(self.db_name)
        curr = conn.cursor()
        # TODO: Only takes 20% as much space if i do a crazy integer format
        # and then save as hex
        curr.execute("""
            CREATE TABLE IF NOT EXISTS digs(
                neighborhood text,
                result integer
            );""")
        curr.executemany("INSERT INTO digs VALUES (?, ?)",
            sql_values)
        conn.commit()
        conn.close()


class DeepMineRandom(DeepMine):
    """A miner that guesses completely at random."""

    def MineProbability(self, neighborhood, total_mines, flag_count):
        return random.random()


def FeaturizeNeighborhoodDense(neighborhood_csv):
    return [int(n) for n in neighborhood_csv.split(",")]


def FeaturizeNeighborhoodSparse(neighborhood_csv):
    """Returns list of active/one-hot column IDs."""
    cell_values = [int(n) for n in neighborhood_csv.split(",")]
    return [(12 * i) + ci + minesweeper.OUT_OF_BOUNDS
            for i, ci in enumerate(cell_values)]


class DeepMineLearner(DeepMine):
    """Another abstract class, this time for miners that can learn."""

    def __init__(self, db_name, radius=2, one_hot_features=False):
        super.__init__(db_name, radius)
        self.one_hot = one_hot_features

    def GetTrainingData(self, max_examples):
        """Turns Dig History table into (X, y) training data pair.

        Depending on self.one_hot, X is either a CSC matrix or a list-of-lists.
        """
        conn = sqlite3.connect(self.db_name)
        curr = conn.cursor()
        curr.execute("SELECT COUNT(1) FROM digs;")
        num_rows = curr.fetchone()[0]
        if num_rows < max_examples:
            query = "SELECT neighborhood, result FROM digs;"
            num_examples = num_rows
        else:
            # (wincing)
            query = """SELECT neighborhood, result FROM digs
                        ORDER BY RANDOM() LIMIT %d""" % (max_examples,)
            num_examples = max_examples
        if self.one_hot:
            rows = []
            cols = []
            data = []
            y = []
            row = 0
            for neigh, result in curr.execute(query):
                y.append(result)
                col_ids = FeaturizeNeighborhoodSparse(neigh)
                cols.extend(col_ids)
                rows.extend([row for _ in col_ids])
                data.extend([1 for _ in col_ids])
            X = sparse.csc_matrix((data, (rows, cols)))
            return (X, y)
        X = []
        y = []
        for neigh, result in curr.execute(query):
            X.append(FeaturizeNeighborhoodDense(neigh))
            y.append(result)
        return X, y


if __name__ == "__main__":
    crazy_ivan = DeepMineRandom("/tmp/deep_mine.db")
    ms_game = minesweeper.BeginnerGame()
    crazy_ivan.PlayGame(ms_game)
