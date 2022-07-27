# DeepMine

Here's me trying to teach my laptop to play Minesweeper.

## Setup

I'm running this on my fairly-old Macbook Pro.  I did some wrangling with
Homebrew to get Python 3.7 running.  From there, I set up a blank virtual
environment and installed Scikit Learn and Pillow:

```
pip install -U scikit-learn
pip install Pillow
```

In total, the environment looks like:

```
$ pip freeze
joblib==0.13.2
numpy==1.16.4
Pillow==6.1.0
scikit-learn==0.21.2
scipy==1.3.0
```

## `minesweeper.py`

`minesweeper.py` has a class, `MinesweeperGame`, that handles the play of an
individual game of Minesweeper.

But it also has a `main()` routine, too, so you can just start playing
Minesweeper in the console:

```
$ python minesweeper.py [difficulty]
```

where using the character `m` for `difficulty` launches a medium-difficulty
game, and `h` launches a hard game. (Any other character, or omitting the
character, launches the default: an easy game.)  It will ask you for one integer
at a time, Row, then Col, to pick a place to dig.  You can't plant flags, so
just dig up all the not-mine spots till you win.

Some more details on the `MinesweeperGame`

*   Games are initialized with a board size and number of mines, and some
    helper methods provide Beginner, Intermediate, and Expert defaults.
    You can also provide a seed value to control the random placement of mines.
*   Provides a way to ask, "what does the board look like near the cell at
    row X, col Y?"
    *   This localized-board-state is called a *neighborhood*
    *   You can ask for an arbitrarily large neighborhood centered at (X, Y) by
        passing in a larger `radius` value.  The method will give you a
        row-major encoding of the board's visible cell values, for the cells
        in a rectangle with one corner at (X - radius, Y - radius) out to
        (X + radius, Y + radius) at the opposite corner.   Sort of an
        "L-infinity"-style radius.
*   Provides some handy enums for encoding board values other than the usual
    digits 0 through 8 -- i.e., how the game state encodes "this cell not yet
    dug" or "this cell has a flag on it."
*   Provides a way to mark a particular (X, Y) square with a flag.
*   Provides a way to dig at a particular (X, Y) square, and tells you whether
    or not you died.  If your dig reveals that the cell had zero neighboring
    mines, the game automatically digs up all its undug neighbors.
*   If you hit a mine, you die!
*   Also, if you try and dig in a square you've already dug, you crack through
    the earth's mantle, fall into a pit of magma, and die!  That rule might be
    unique to this implementation.
*   Provides a way to print the current board to the command line.


## `deep_mine.py`

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
totally ignores any information you provide it.

There's another class, `DeepMineLearner`, which currently has a method for
fetching and parsing training data out of the Dig History table.  This will
serve as a base on which ML-backed agents are implemented.

## Coming soon

*   Support flag-planting on the part of the agents
*   More and better DeepMine agents, which can read the Dig History table and
    train a `MineProbability` model.  Easy models I have in mind:
    *   Decision trees
    *   Logistic regression with some kind of polynomial kernel
    *   Anything else that seems to be just sitting around in SciKit Learn
*   Add a method to `MinesweeperGame` that renders the current board as a PNG
*   The Dig History table is really inefficient in terms of storing
    neighborhoods, I could make it 5x smaller by just hacking together an
    integer representation of a neighborhood
*   My actual goal here is to let this whole thing act as a Twitter Bot, which
    posts little play-by-play images of the game board as the agent digs around
    hunting mines.
