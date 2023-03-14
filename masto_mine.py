"""Group-play of beginner-sized Minesweeper games via a Mastodon account.

This job runs a series of Minesweeper games, where each game is always of
size {8 rows, 8 columns, 10 mines}.  Each run of this job increments a game by
one move per run, persisting state of all games in a SQLite table.

How this job works:

1.  The job wakes up,
2.  parses the job-flag instructions from the command line,
3.  loads in the history of moves made in the most-recent game in the DB
    (or notices that the most recent game is finished a new game needs creating)
4.  creates a fresh `minesweeper.MinesweeperGame` object,
5.  replays the move history (from Step 3) on that MSGame object,
6.  picks a move to play,
  a) if this is a new game, just posts a "Welcome to a new game of Minesweeper!"
     message as the "move" for this run.
  b) if this is an ongoing game, look for replies made to the last post this
     bot made, and sees if any are telling the bot what move to make. If so,
     that's our move!
  c) Otherwise, if no human-provided move can be found in the replies, pick a
     move at random. (Maybe use a smarter alternative for this someday.)
7.  applies the move to the board and posts the board state,
8.  stores this latest move back in the DB,
9.  and exits, waiting for someone to run it again with the next move someday.

Example usage:

   $ python masto_mine.py games.db mdn_account.secret

Where `games.db` is a SQLite3 database file and `mdn_account.secret` is a
credentials file for a Mastodon account, as generated by Mastodon.py.
"""

from __future__ import annotations

import dataclasses
import enum
import json
import minesweeper
import random
import sqlite3
import sys
import time

from collections.abc import Sequence

from mastodon import Mastodon


# ASCII form of the game board's row and column header letters:
_ROW_HEADERS = ('a', 'b', 'c', 'd', 'e', 'f', 'g', 'h')
_COL_HEADERS = ('i', 'j', 'k', 'l', 'n', 'q', 'r', 't')


_CREATE_TABLE_QUERY = """
    CREATE TABLE IF NOT EXISTS games (
        game_id INTEGER,
        move_id INTEGER,
        command TEXT CHECK( command IN ('new', 'dig', 'flag') ),
        gridpoint_row INTEGER CHECK( gridpoint_row >= 0 AND gridpoint_row < 8 ),
        gridpoint_col INTEGER CHECK( gridpoint_col >= 0 AND gridpoint_col < 8 ),
        post_id TEXT NOT NULL,
        PRIMARY KEY(game_id, move_id)
    );
"""

_UPDATE_STATE_QUERY = """
    INSERT INTO games (
        game_id, move_id, command, gridpoint_row, gridpoint_col, post_id)
    VALUES (?, ?, ?, ?, ?, ?);
"""

# The moves from the latest game, in play order.
_LATEST_GAME_QUERY = """
    SELECT
        game_id,
        move_id,
        command,
        gridpoint_row,
        gridpoint_col,
        post_id
    FROM games
    WHERE game_id = ( SELECT MAX(game_id) FROM games )
    ORDER BY move_id;
"""

_WELCOME_TWEET_TEMPLATE = """Welcome to a #NewGame of #Minesweeper!
Tell this bot what move to make: reply with 'dig A,K' or 'flag D,Q'.

Game {game_num}
"""

_MOVE_TWEET_TEMPLATE = """#Minesweeper Game {game_num}, Move {move_num}:
{player} says: '{cmd} at {row}, {col}!'
{results}
"""

_COUNTS_TEMPLATE = "Mines: {num_mines}\nFlags: {num_flags}\n"


@enum.unique
class Command(enum.Enum):
    """A command for updating state of the minesweeper game."""
    NEW = 'NEW'
    DIG = 'DIG'
    FLAG = 'FLAG'


@dataclasses.dataclass(frozen=True)
class GameState:
    """A game's state of play."""
    game: minesweeper.MinesweeperGame
    game_id: int
    move_id: int  # This is -1 when no move's been made yet in this game.
    post_id: str  # This is empty when no move's been made yet.


@dataclasses.dataclass(frozen=True)
class GameMove:
    """Move to make in Minesweeper."""
    command: Command
    move_maker: str
    gridpoint_row: int
    gridpoint_col: int


def game_seed(db_filename: str, game_id: int) -> str:
    return f'{game_id} Super secret salt, no peeking {db_filename} {game_id}'


def load_game_state(
    db_cursor: sqlite3.Cursor, db_filename: str) -> GameState:
    """Fetches the last game, game ID, and move ID entered in this DB file.

    Args:
        db_cursor: A cursor pointing to the game state database.
        db_filename: The filename for this SQLite database.

    Returns:
        A game state, ready for next
    """
    db_cursor.execute(_LATEST_GAME_QUERY)  # Note: this ORDERS BY move_id
    rows = db_cursor.fetchall()
    game = None
    game_id = None
    if not rows:
        game_id = 1
        move_id = -1
        game = minesweeper.MinesweeperGame.Beginner(
            seed=game_seed(db_filename=db_filename, game_id=game_id))
        return GameState(
            game=game, game_id=game_id, move_id=move_id, post_id="")
    for expected_move_id, row in enumerate(rows):
        row_game_id, move_id, cmd_str, g_row, g_col, post_id = row
        if game_id is None:
            game_id = row_game_id
            game = minesweeper.MinesweeperGame.Beginner(
                seed=game_seed(db_filename=db_filename, game_id=game_id))
        else:
            assert game_id == row_game_id
        # Ensure the move IDs are consecutive integers starting at 0:
        if move_id != expected_move_id:
            raise ValueError(
                f"Expected move ID of {expected_move_id} "
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
        assert command is not Command.NEW
        apply_move(game, command, gridpoint_row=g_row, gridpoint_col=g_col)
    if game.Dead() or game.Won():
        game_id += 1
        move_id = -1
        game = minesweeper.MinesweeperGame.Beginner(
            seed=game_seed(db_filename=db_filename, game_id=game_id))
        return GameState(
            game=game, game_id=game_id, move_id=move_id, post_id="")
    return GameState(
        game=game, game_id=game_id, move_id=move_id, post_id=post_id)


def apply_move(ms_game: minesweeper.MinesweeperGame, command: Command,
               gridpoint_row: int, gridpoint_col: int) -> None:
    """Updates ms_game according to given command."""
    if command is Command.DIG:
        ms_game.Dig(gridpoint_row, gridpoint_col)
    elif command is Command.FLAG:
        ms_game.PlantFlag(gridpoint_row, gridpoint_col)
    else:
        raise ValueError(f"Unsupported apply_move command: {command}")


def calculate_next_move(game_state: GameState) -> GameMove:
    if game_state.move_id == -1:
        return GameMove(command=Command.NEW, move_maker="",
                        gridpoint_row=0, gridpoint_col=0)
    # TODO: Try to load and parse replies to bot's previous post.
    random.seed(time.time())
    return GameMove(
        command=(Command.DIG if random.random() < 0.5 else Command.FLAG),
        move_maker="Guessing randomly...",
        gridpoint_row=random.randint(0, 7),
        gridpoint_col=random.randint(0, 7))


# TODO: Start posting someday
def welcome_post_contents(game_state: GameState) -> str:
    """What to post when starting a game."""
    return (_WELCOME_TWEET_TEMPLATE.format(game_num=game_state.game_id) +
            _COUNTS_TEMPLATE.format(
                num_mines=game_state.game.NumMinesTotal(),
                num_flags=game_state.game.NumFlagged(),
            ) + "\n" +
            game_state.game.AsEmoji())


def move_result_post_contents(game_state: GameState, move: GameMove) -> str:
    """What to post when you've just made a move in the game."""
    if game_state.game.Dead():
        results = "💥 KABOOM! 💥\n"
    elif game_state.game.Won():
        results = "🎉 WE WIN! 🎉\n"
    else:
        results = _COUNTS_TEMPLATE.format(
            num_mines=game_state.game.NumMinesTotal(),
            num_flags=game_state.game.NumFlagged())
    return (_MOVE_TWEET_TEMPLATE.format(
                game_num=game_state.game_id,
                move_num=game_state.move_id,
                player=move.move_maker,
                cmd=move.command.name,
                row=_ROW_HEADERS[move.gridpoint_row].upper(),
                col=_COL_HEADERS[move.gridpoint_col].upper(),
                results=results
            ) +
            game_state.game.AsEmoji())


def get_post_contents(game_state: GameState, move: GameMove) -> str:
    """What to post, for any occasion."""
    if game_state.move_id == 0:
        return welcome_post_contents(game_state)
    return move_result_post_contents(game_state, move)


def update_game_state(db_cursor: sqlite3.Cursor,
                      game_id: int,
                      move_id: int,
                      command: Command,
                      gridpoint_row: int,
                      gridpoint_col: int,
                      post_id: str) -> None:
    """Updates the DB's game state table with the latest move."""
    db_cursor.execute(
        _UPDATE_STATE_QUERY,
        (game_id, move_id, command.name.lower(),
         gridpoint_row, gridpoint_col, post_id)
    )


def main():
    db_filename = sys.argv[1]
    mdn_creds_filename = sys.argv[2]

    db_conn = sqlite3.connect(db_filename)
    db_cursor = db_conn.cursor()
    db_cursor.execute(_CREATE_TABLE_QUERY)

    prev_game_state = load_game_state(db_cursor, db_filename)
    game_id = prev_game_state.game_id
    ms_game = prev_game_state.game
    this_move_id = prev_game_state.move_id + 1

    this_move = calculate_next_move(prev_game_state)
    if this_move.command is not Command.NEW:
        apply_move(ms_game,
                   command=this_move.command,
                   gridpoint_row=this_move.gridpoint_row,
                   gridpoint_col=this_move.gridpoint_col)
    this_game_state = GameState(
        game=ms_game, game_id=game_id, move_id=this_move_id, post_id=""
    )
    print(get_post_contents(this_game_state, this_move))

    # No posting, yet.
    """
    post_contents = get_post_contents(flags, this_move_id, ms_game)
    print(len(post_contents))
    print(post_contents)
    request_data = {'status': post_contents}
    if last_post_id is not None:
        request_data['in_reply_to_status_id'] = last_post_id
        request_data['auto_populate_reply_metadata'] = True
    resp = requests.post(url=POST_TWEET_URL, data=request_data, auth=oauth)
    if not resp.ok:
        print(resp.text)
    resp.raise_for_status()
    this_post_id = resp.json().get('id_str', None)
    print(f'Twitter response: {resp.status_code} {resp.reason};',
          f'Tw. ID {this_post_id}')
    if this_post_id is None:
        print(resp.text)
        raise RuntimeError("For some reason, posting failed!!")
    """

    update_game_state(db_cursor, game_id, this_move_id, this_move.command,
                      this_move.gridpoint_row, this_move.gridpoint_col,
                      "")
    db_conn.commit()
    db_conn.close()


if __name__ == "__main__":
    main()
