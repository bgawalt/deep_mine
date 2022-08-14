# `tweet_mine.py`

Instead of one person enjoying a private game in their own terminal, let's
play together on Twitter.com!

Each run of this job increments a Minesweeper game by one move, and tweets out
the resulting board in emoji format.  Repeated runs of this job creates one long
thread for the game.  The idea is that the followers of the account tweeting the
game are encouraged to join in and shout out where to dig.

Here's an example tweet
([Move 3 of Game 0](https://twitter.com/bgawalt/status/1558890063584301064)):

![Screenshot of https://twitter.com/bgawalt/status/1558890063584301064](tweet_mine.png|width=250px)

Unlike `minesweeper.py`'s `main()` routine, where game state is persisted across
the full run of the game with a single `MinesweeperGame` object in memory, this
job keeps game state in a SQLite table on disk.

An outline of a single run of `tweet_mine.py`:

1.  The job wakes up,
2.  parses the job-flag instructions from the command line,
2.  loads in the history of moves made in the game so far from the DB,
3.  creates a fresh `minesweeper.MinesweeperGame` object,
4.  replays the move history on that MSGame object,
5.  plays the new move defined by the job flags on the MSGame,
6.  tweets out the board state as of this latest move,
7.  stores the latest move back in the DB,
8.  and exits, waiting for someone to run it again with the next move someday.

There's *no automation yet* the way you'd see in most Twitter bots: I'm simply
receiving notifications of replies sent to my personal Twitter, and manually
ferrying the instructions people give me onto my laptop's command line.


## Usage

Execute this main() routine with the following positional command line flags
to perform one move in the game (with details on each flag below):

```shell
$ python tweet_mine.py \
    sqilte_file123.db \
    oauth_config.json \
    player \
    command \
    gridpoint
```

*  `sqlite_file123.db`: A file to be used as a SQLite3 database for this game.
        It will track the moves issued so far, and the name of this file is
        the basis for the seed value used to initially place the mines.
        *  When `command` is 'new', this file should not exist (i.e, the file
            will be created by this job).
        *  Otherwise, this job expects exactly one table to exist in the
            database.  See "The Database" below for details.
        *  For embarassingly hacky reasons: this filename *must contain* some
           digits -- these digits are extracted and used as a "Game #123"
           identifier when tweeting out the game board state.
*  `oauth_config.json`: A JSON file that contains OAuth2 credentials for posting
        to a Twitter account. Expects string fields of:
        *  'consumer_key'
        *  'consumer_secret'
        *  'access_key'
        *  'access_secret'
*  `player`: Twitter account @-handle of the person issuing the new move
*  `command`: A "magic string" matching one of the following commands:
        *  'new': Initialize the game by creating a table in the SQLite file
        *  'dig': Make a game move by digging at the given grid point
        *  'flag': Make a game move by planting a flag at the given grid point
        *  (matching is case-insensitive)
*  `gridpoint`: A three-character string, where the middle character is a comma,
        of format 'r,c', where 'r' (row) and 'c' (col) have the following valid
        values:
        *  'r' in [a, b, c, d, e, f, g, h]
        *  'c' in [i, j, k, l, n, q, r, t]
        *  (lookup is case-insensitive; 'A,t' and 'f,N' both work fine.)
        *  (See "About the row/column labels" below to make this make sense!)

TODO: Positional flags are fragile but easy to code up; migrate to argparse or
    Abseil flags or such when you've got time for cleanup.

TODO: Is a JSON file hanging around with OAuth creds really the best we can do,
    security wise?  I have no idea!!


## Updating State via The Database

The database file is used to track state across the many moves it takes to play
a minesweeper game.  It does so with one table in the database.

The database is used differently depending on the value of the `command` flag.

### When `command` is `'new'`

When starting a new game, this program expects `sqlite_file.db` to be empty.
Its first step will be to create a table that will store the moves made.

This table is called 'game_state' with columns:

*  'move_id', INTEGER: A zero-indexed identifier for moves made so far.
*  'command', TEXT: Either 'new', 'dig' or 'flag'.
*  'gridpoint_row', INTEGER: The row in which to dig/flag.
*  'gridpoint_col', INTEGER: The column in which to dig/flag.
*  'tweet_id', TEXT: The tweet ID string for the tweet this move generated.

Inserts to this table will come immediately following each call to Twitter's
"send tweet" API.

The very first such tweet will be a "Welcome to Minesweeper"
message with brief instructions and an emoji rendering of an undug board.
This will be the start of this game's Twitter thread.  The job will insert
`{move_id: 0, command: 'new', gridpoint: '', tweet_id: '[tweet ID]'}` as the
first row in the table.

Then the job exits!  Hopefully someone replies to that Welcome tweet and starts
digging.

### When `command` is `'flag'` or `'dig'`

If this job is launched with either of the other two commands, it will:

1.  Connect to the given SQLite DB file
2.  Load in all the move-rows inserted so far in table `'game_state'`, and make
    sure they make sense:
    *  The `move_id` fields are consecutive integers starting at 0
    *  The `command` fields are valid: 'new' for move 0; 'flag'/'dig' otherwise
    *  The `gridpoint` positions are sensible (see below subsection for row and
        column naming scheme)
    *  Other checks, too, probably; any of them is a chance to die and emit an
        "invalid state" exception message on the way out
3.  Instantiate a game board with a call to `MinesweeperGame.BeginnerGame` with
    a seed based on hashing the DB file name.  (This means regenerating the same
    ten mine positions each time this job runs, without having to explicitly
    materialize them.)
4.  For N moves retrieved from the DB, replay moves 1 through N - 1.
    (If any of these moves results in digging a mine -- raise an exception!
    You shouldn't try playing a game where there's already a fatal dig on file.)
5.  Apply the move issued via the command line flags given to this run of the
    job.
6.  Tweet the resulting board, and mention the Twitter user (as provided in the
    `player` command line flag above).
7.  Insert the details (including the ID of the tweet from Step 6) into the
    `'game_state'` table.

Then the job exits!


## Row/column names

The minesweeper boards are rendered in emoji.  I have abused the Regional
Indicator Symbols to render row and column labels as letters.  Ordinarily, those
Regional Indicators are meant to be paired up, where they can collapse together
and be replaced by the region encoded by that two-letter pair.

With the rows, I only ever follow the row-header emoji with a
non-Regional-Indicator emoji: it's row-header, then one of the symbols used to
represent a game board grid point.  So it's easy to just use A through H for
the row headers.

For the column-header emoji, though: they necessarily all appear on the same
line.  By trial and error, I found that the sequence:

    [I, J, K, L, N, Q, R, T]

never produces an ordered pair that collapses into a recognized two-letter
region code.  (For instance, trying to make consecutive columns N and O would
just result in the flag for Norway, instead of two useful column header
symbols.  So instead, it's N then Q!)


## Future work

*  Load in replies to the latest tweet automatically, and parse them for
    minesweeping instructions
*  Quote tweet the tweet with the latest minesweeping instructions when posting
    the results of the sweep command
