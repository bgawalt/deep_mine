"""Group-play of a beginner-sized Minesweeper game via a Twitter account.

Each run of this job increments a Minesweeper game by one move, and tweets out
the resulting board in emoji format.  Repeated runs of this job creates one long
thread for the game.  The idea is that the followers of the account Tweeting the
game are encouraged to join in and shout out where to dig.


## Usage

Execute this main() routine with the following positional command line flags
to perform one move in the game (with details on each flag below):

```
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
"""

from __future__ import annotations

import dataclasses
import enum
import json
import minesweeper
import requests
import requests_oauthlib
import sqlite3
import sys

from collections.abc import Sequence


# ASCII form of the game board's row and column header letters:
_ROW_HEADERS = ('a', 'b', 'c', 'd', 'e', 'f', 'g', 'h')
_COL_HEADERS = ('i', 'j', 'k', 'l', 'n', 'q', 'r', 't')

# Where to send tweets:
POST_TWEET_URL = 'https://api.twitter.com/1.1/statuses/update.json'

_CREATE_TABLE_QUERY = """
    CREATE TABLE game_state (
        move_id integer,
        command text,
        gridpoint_row integer,
        gridpoint_col integer,
        tweet_id text
    );
"""

_UPDATE_STATE_QUERY = """
    INSERT INTO game_state (
        move_id, command, gridpoint_row, gridpoint_col, tweet_id)
    VALUES (?, ?, ?, ?, ?);
"""

_FETCH_GAME_MOVES_QUERY = """
    SELECT
        move_id,
        command,
        gridpoint_row,
        gridpoint_col,
        tweet_id
    FROM game_state
    ORDER BY move_id;
"""

_WELCOME_TWEET_TEMPLATE = """It's #Minesweeper, Game {game_num}!
Reply with 'dig A,K' or 'flag D,Q'.
"""

_MOVE_TWEET_TEMPLATE = """#Minesweeper Game {game_num}, Move {move_num}:
@{player} says: '{cmd} at {row}, {col}!'
{results}
"""

_COUNTS_TEMPLATE = "Mines: {num_mines} ({num_flags} flags):\n"


@enum.unique
class Command(enum.Enum):
    """A command for updating state of the minesweeper game."""
    NEW = 'NEW'
    DIG = 'DIG'
    FLAG = 'FLAG'


@dataclasses.dataclass(frozen=True)
class CommandLineFlags():
    """Instructions passed in to this job at runtime, lightly parsed."""
    sqlite_filename: str  # TODO: Use pathlib
    oauth_config_filename: str  # TODO: Use pathlib
    player: str
    command: Command
    gridpoint_row: int  # If digging or flagging, must be in range [0, 7]
    gridpoint_col: int  # If digging or flagging, must be in range [0, 7]

    def __post_init__(self):
        try:
            self.game_num()
        except ValueError:
            raise ValueError(f"No digits found in {self.sqlite_filename}")
        if self.command is not Command.NEW:
            if self.gridpoint_row < 0 or self.gridpoint_row > 8:
                raise ValueError(
                    f"gridpoint_row out of bounds: {self.gridpoint_row}")
            if self.gridpoint_col < 0 or self.gridpoint_col > 8:
                raise ValueError(
                    f"gridpoint_row out of bounds: {self.gridpoint_col}")

    def game_num(self) -> int:
        return int("".join(ch for ch in self.sqlite_filename if ch.isdigit()))

    @classmethod
    def from_argv(cls, argv: Sequence[str]) -> CommandLineFlags:
        """Parses system arguments into CommandLineFlags object."""
        if len(argv) != 6:
            raise ValueError(
                f"Incorrect number of command line arguments: {argv}")
        _, sqlfile, oauthfile, player, cmd_str, grid = argv
        try:
            command = Command[cmd_str.upper()]
        except KeyError:
            raise ValueError(f'Invalid command arg: {cmd_str}')
        if command is Command.NEW:
            g_row = -1
            g_col = -1
        else:
            if len(grid) != 3:
                raise ValueError(f"Invalid gridpoint arg: {grid} (bad length)")
            if grid[1] != ",":
                raise ValueError(
                    f"Invalid gridpoint arg: {grid} (missing comma)")
            row_ch, col_ch = grid.lower().split(",")
            g_row = _ROW_HEADERS.index(row_ch)
            g_col = _COL_HEADERS.index(col_ch)
        return CommandLineFlags(
            sqlite_filename=sqlfile,
            oauth_config_filename=oauthfile,
            player=player,
            command=command,
            gridpoint_row = g_row,
            gridpoint_col = g_col
        )


def oauth_from_config_file(config_filename: str) -> requests_oauthlib.OAuth1:
    with open(config_filename) as infile:
        config = json.load(infile)
    return requests_oauthlib.OAuth1(
        client_key=config['consumer_key'],
        client_secret=config['consumer_secret'],
        resource_owner_key=config['access_key'],
        resource_owner_secret=config['access_secret']
    )


def initialize_game_state(db_cursor: sqlite3.Cursor) -> None:
    """Creates the game state table, or dies trying."""
    try:
        db_cursor.execute(_CREATE_TABLE_QUERY)
    except sqlite3.OperationalError as op_err:
        raise RuntimeError(
        "Seems like you tried initializing a game via 'NEW' on a DB file"
        "that already has a game going.") from op_err


def load_game_state(db_cursor: sqlite3.Cursor,
                    ms_game: minesweeper.MinesweeperGame) -> Tuple[int, str]:
    """Fetches, validates, and applies game moves already on file.

    Most of the value here is just in double checking that the moves on file
    are sensible and reflect a valid, ongoing game.

    Args:
        db_cursor: A cursor pointing to the game state database.
        ms_game: The current game, with mines properly seeded.

    Returns:
        First element: The next move ID expected to be inserted.
        Second element: The tweet ID corresponding to the last move.
    """
    db_cursor.execute(_FETCH_GAME_MOVES_QUERY)  # Note: this ORDERS BY move_id
    for expected_move_id, row in enumerate(db_cursor.fetchall()):
        move_id, cmd_str, g_row, g_col, tw_id = row
        # Ensure the move IDs are consecutive integers starting at 0:
        if move_id != expected_move_id:
            raise ValueError(
                f"Expected move ID of {expected_move_id}"
                f"but got a row like {row}"
            )
        # Parse the command into the nice enum version:
        try:
            command = Command[cmd_str.upper()]
        except KeyError:
            raise ValueError(f"Unrecognized command in row {row}")
        # The first move ("move 0") is always a no-op of NEW:
        if move_id == 0:
            if command is not Command.NEW:
                raise ValueError(f"Move 0 must have command NEW; got row {row}")
            continue
        apply_move(ms_game, command, gridpoint_row=g_row, gridpoint_col=g_col)
        if ms_game.Dead():
            raise RuntimeError("This game already ended (in death)!")
        if ms_game.Won():
            raise RuntimeError("This game already ended (in victory)!")
    return (move_id + 1, tw_id)


def apply_move(ms_game: minesweeper.MinesweeperGame, command: Command,
               gridpoint_row: int, gridpoint_col: int) -> None:
    """Updates ms_game according to given command."""
    if command is Command.DIG:
        ms_game.Dig(gridpoint_row, gridpoint_col)
    elif command is Command.FLAG:
        ms_game.PlantFlag(gridpoint_row, gridpoint_col)
    else:
        raise ValueError(f"Unsupported apply_move command: {command}")


def welcome_tweet_contents(job_flags: CommandLineFlags,
                           ms_game: minesweeper.MinesweeperGame) -> str:
    """What to tweet when starting a game."""
    return (_WELCOME_TWEET_TEMPLATE.format(game_num=job_flags.game_num()) +
            _COUNTS_TEMPLATE.format(num_mines=ms_game.NumMinesTotal(),
                                    num_flags=ms_game.NumFlagged()) +
            "\n" +
            ms_game.AsEmoji())


def move_result_tweet_contents(job_flags: CommandLineFlags, move_id: int,
                               ms_game: minesweeper.MinesweeperGame) -> str:
    """What to tweet when you've just made a move in the game."""
    if ms_game.Dead():
        results = "💥 KABOOM! 💥\n"
    elif ms_game.Won():
        results = "🎉 YOU WIN! 🎉\n"
    else:
        results = _COUNTS_TEMPLATE.format(num_mines=ms_game.NumMinesTotal(),
                                          num_flags=ms_game.NumFlagged())
    return (_MOVE_TWEET_TEMPLATE.format(
                game_num=job_flags.game_num(),
                move_num=move_id,
                player=job_flags.player,
                cmd=job_flags.command.name,
                row=_ROW_HEADERS[job_flags.gridpoint_row].upper(),
                col=_COL_HEADERS[job_flags.gridpoint_col].upper(),
                results=results
            ) +
            ms_game.AsEmoji())


def get_tweet_contents(job_flags: CommandLineFlags, move_id: int,
                       ms_game: minesweeper.MinesweeperGame) -> str:
    """What to tweet, for any occasion."""
    if move_id == 0:
        return welcome_tweet_contents(job_flags, ms_game)
    return move_result_tweet_contents(job_flags, move_id, ms_game)


def update_game_state(db_cursor: sqlite3.Cursor,
                      move_id: int,
                      command: Command,
                      gridpoint_row: int,
                      gridpoint_col: int,
                      tweet_id: str) -> None:
    """Updates the DB's game state table with the latest move."""
    db_cursor.execute(
        _UPDATE_STATE_QUERY,
        (move_id, command.name, gridpoint_row, gridpoint_col, tweet_id)
    )


def main():
    flags = CommandLineFlags.from_argv(sys.argv)
    oauth = oauth_from_config_file(flags.oauth_config_filename)

    db_conn = sqlite3.connect(flags.sqlite_filename)
    db_cursor = db_conn.cursor()
    hash_target = 'A super secret salt; no peeking ' + flags.sqlite_filename
    ms_game = minesweeper.MinesweeperGame.Beginner(seed=hash_target)

    # Start with default values corresponding to a new game:
    this_move_id = 0
    last_tweet_id = None
    if flags.command is Command.NEW:
        initialize_game_state(db_cursor)
        db_conn.commit()
    else:
        this_move_id, last_tweet_id = load_game_state(db_cursor, ms_game)
        # Update these values away from the "new game" defaults:
        apply_move(ms_game, flags.command, flags.gridpoint_row,
                   flags.gridpoint_col)

    tweet_contents = get_tweet_contents(flags, this_move_id, ms_game)
    print(len(tweet_contents))
    print(tweet_contents)
    request_data = {'status': tweet_contents}
    if last_tweet_id is not None:
        request_data['in_reply_to_status_id'] = last_tweet_id
        request_data['auto_populate_reply_metadata'] = True
    resp = requests.post(url=POST_TWEET_URL, data=request_data, auth=oauth)
    if not resp.ok:
        print(resp.text)
    resp.raise_for_status()
    this_tweet_id = resp.json().get('id_str', None)
    print(f'Twitter response: {resp.status_code} {resp.reason};',
          f'Tw. ID {this_tweet_id}')
    if this_tweet_id is None:
        print(resp.text)
        raise RuntimeError("For some reason, tweeting failed!!")

    update_game_state(db_cursor, this_move_id, flags.command,
                      flags.gridpoint_row, flags.gridpoint_col,
                      this_tweet_id)
    db_conn.commit()
    db_conn.close()


if __name__ == "__main__":
    main()
