# `minesweeper.py`

`minesweeper.py` has a class, `MinesweeperGame`, that handles the play of an
individual game of Minesweeper.

But it also has a `main()` routine, too, so you can just start playing
Minesweeper in the console:

```shell
$ python minesweeper.py [difficulty]
```

where using the character `m` for `difficulty` launches a medium-difficulty
game, and `h` launches a hard game. (Any other character, or omitting the
character, launches the default: an easy game.)  It will ask you for one integer
at a time, Row, then Col, to pick a place to dig.  (Rows and columns are
zero-indexed.)  You can't plant flags, so just dig up all the not-mine spots
till you win.

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
