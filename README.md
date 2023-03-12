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
additional/non-standard libraries needed for `minesweeper.py` and
`tweet_mine.py` to function.

`masto_mine.py` *does* need `Mastodon.py`:

```
$ pip3 install Mastodon.py
```

To use the not-yet-completed `deep_mine.py`, you'll someday need Scikit Learn:

```
pip install -U scikit-learn
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


## `masto_mine.py`

The file `masto_mine.py` let's you play a long-running series of 8x8 games
on a Mastodon account.  (Mine is going to run at `@minesweeper@botsin.space`.)

It's not done yet!  It can track serial game state in a local SQLite file,
but it's not trying to fedipost yet.

See [masto_mine.py](doc/masto_mine.md) for a full explainer.


## `tweet_mine.py`

The file `tweet_mine.py` provides a way to play Minesweeper on a Twitter
account.

This may no longer work -- the Twitter API is in a weird place as of this
writing, and my use of the site is on hold for the foreseeable future.

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
