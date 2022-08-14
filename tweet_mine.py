"""Group-play of a beginner-sized Minesweeper game via a Twitter account.

This job runs a Minesweeper game (always of size 8 rows, 8 columns, 10 mines)
one move at a time, persisting state in a SQLite table:

1.  The job wakes up,
2.  parses the job-flag instructions from the command line,
2.  loads in the history of moves made in the game so far from the DB,
3.  creates a fresh `minesweeper.MinesweeperGame` object,
4.  replays the move history on that MSGame object,
5.  plays the new move defined by the job flags on the MSGame,
6.  tweets out the board state as of this latest move,
7.  stores the latest move back in the DB,
8.  and exits, waiting for someone to run it again with the next move someday.

Example usage, with required positional flags:

```
$ python tweet_mine.py \
    sqilte_file123.db \
    oauth_config.json \
    player \
    command \
    gridpoint
```

See `doc/tweet_mine.md` for full details.
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
