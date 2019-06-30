import deep_mine
import minesweeper

import random


class DeepMineRandom(deep_mine.DeepMine):
    """A miner that guesses completely at random."""

    def MineProbability(self, neighborhood, total_mines, flag_count):
        return random.random()


if __name__ == "__main__":
    crazy_ivan = DeepMineRandom("./deep_mine.db")
    ms_game = minesweeper.BeginnerGame()
    crazy_ivan.PlayGame(ms_game, fps=0.7)
