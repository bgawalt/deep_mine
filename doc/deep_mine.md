# `deep_mine.py`

`deep_mine.py` provides a base class, `DeepMine`, which represents an agent
capable of playing a game of Minesweeper.  Initialize it by passing it a file
name/path to a file that you'd like to use as a SQLite3 database for recording
game outcomes, as well as an integer radius value to use when asking a game
board for neighborhood information.

The method `PlayGame` accepts a `MinesweeperGame` object, preferably a freshly
initialized game.  It then plays the game by sending the game repeated `Dig`
commands.

It decides where to dig by asking the game for neighborhood information at every
cell on the board.  Each of these neighborhoods is passed to `MineProbability`,
which returns a value between zero and one.  Whichever cell-neighborhood had
the lowest mine probability is the cell that gets dug up.  This continues until
the DeepMine agent dies (by hitting a mine or digging in an already-dug spot)
or wins (by digging up so many cells that the number of undug cells equals
the number of mines in the game).

Every time the agent digs up a cell, it writes down the neighborhood it saw
before digging as well as the "did I survive" result of the dig.  It stores this
as a SQLite3 database file at the location specified at agent initialization.
The database has exactly one table, named `digs`.  There are two columns in it:

1.  `neighborhood`, a CSV string of cell values visible on the board prior to
    the dig.  A digit from 0 to 8 counts the number of mines next to the cell.
    A value below 0 is a special enum for things like "cell is outside game
    board boundaries" or "cell has not yet been dug up."
2.  `result`, an integer of value either 0 or 1.  A 1 means the agent survived
    digging in the cell at the center of this neighborhood; a 0 means the agent
    died.

There's no notion of a DeepMine agent planting flags right now.  I could imagine
a smart-enough agent benefitting from that capability.

`deep_mine.py` only has one true agent implemented right now: `DeepMineRandom`.
Its `MineProbability` method just picks random values between 0 and 1 and
totally ignores any neighborhood information you provide it.

There's another class, `DeepMineLearner`, which currently has a method for
fetching and parsing training data out of the Dig History table.  This will
serve as a base on which ML-backed agents are implemented.

## Dependencies

To use this not-yet-completed `deep_mine.py`, I set up a blank virtual
environment and installed Scikit Learn:

```
pip install -U scikit-learn
```

but I'm not doing anything with it yet.

## Coming soon

*   Support flag-planting on the part of the DeepMine agents
*   More and better DeepMine agents, which can read the Dig History table and
    train a `MineProbability` model.  Easy models I have in mind:
    *   Decision trees
    *   Logistic regression with some kind of polynomial kernel
    *   Anything else that seems to be just sitting around in SciKit Learn
*   Add a method to `MinesweeperGame` that renders the current board as a PNG.
    ("Render as Emoji" was added to support tweeting, but that doesn't scale
    well past the 8x8 beginner board size.)
*   The Dig History table is really inefficient in terms of storing
    neighborhoods, I could make it 5x smaller by just hacking together an
    integer representation of a neighborhood
*   My actual goal here is to let this whole thing act as a Twitter Bot, which
    posts little play-by-play images of the game board as the agent digs around
    hunting mines.
