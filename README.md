# DeepMine

A suite that takes the game of
[Minesweeper](https://en.wikipedia.org/wiki/Minesweeper_(video_game)) and:

1.  Plays it on the command line ([`minesweeper.py`](doc/minesweeper.md))
2.  Plays it on Twitter ([`tweet_mine.py`](doc/tweet_mine.md))
3.  Machine-learns an agent that can play on its own
    ([`deep_mine.py`](doc/deep_mine.md))

The original goal was (3) but it turns out (1) and (2) were fun waypoints to
explore and build out!  So (1) and (2) are done, but (3) is still a
work-in-progress.

## Setup

I'm running this on my fairly-old Macbook Pro.  I did some wrangling with
Homebrew to get Python 3.9 running.   As far as I can tell, there are no
additional/non-standard libraries needed for`minesweeper.py` and `tweet_mine.py`
to function.

To use the not-yet-completed `deep_mine.py`, I set up a blank virtual
environment and installed Scikit Learn and Pillow:

```
pip install -U scikit-learn
pip install Pillow
```

In total, that environment looks like:

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
individual game of Minesweeper.  It also has a `main()` routine, too, so you can
just start playing Minesweeper in the console:

```
$ python minesweeper.py [difficulty]
```

where using the character `m` for `difficulty` launches a medium-difficulty
game, and `h` launches a hard game. (Any other character, or omitting the
character, launches the default: an easy game.)

See [minesweeper.md](doc/minesweeper.md) for a full explainer.


## `tweet_mine.py`

The file `tweet_mine.py` provides a way to play Minesweeper on a Twitter
account.

See [tweet_mine.md](doc/tweet_mine.md) for a full explainer.


## `deep_mine.py`

`deep_mine.py` provides a base class, `DeepMine`, which represents an agent
capable of playing a game of Minesweeper.  An individual agent relies on a
SQLite3 database for recording game outcomes, as well as an integer radius value
to use when asking a game board for neighborhood information.

The idea is someday, I'll implement a variety of learners that make use of this
basic framework, and then somehow show off their ability to learn and master
minesweeping.  Still a work in progress!

See [deep_mine.md](doc/deep_mine.md) for a full explainer.
