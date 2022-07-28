import deep_mine
import minesweeper

from scipy import sparse


def FeaturizeNeighborhoodDense(neighborhood_csv):
    return [int(n) for n in neighborhood_csv.split(",")]


def FeaturizeNeighborhoodSparse(neighborhood_csv):
    """Returns list of active/one-hot column IDs."""
    cell_values = [int(n) for n in neighborhood_csv.split(",")]
    # OUT_OF_BOUNDS is the lowest-valued cell-contents code
    return [(12 * i) + ci + int(minesweeper.CellValue.OUT_OF_BOUNDS)
            for i, ci in enumerate(cell_values)]


class DeepMineLearner(deep_mine.DeepMine):
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
