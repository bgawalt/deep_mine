"""Delete every Mastodon post on file.

Usage:

    $ python delete_em_all.py games.db masto_acct.secret

This was useful when testing the bot live in production.  Wiping up messes.
"""

import sys
import sqlite3
import time

from mastodon import Mastodon

def main():
    db_filename = sys.argv[1]
    db_conn = sqlite3.connect(db_filename)
    db_cursor = db_conn.cursor()
    # Set up the Mastodon client:
    mdn_creds_filename = sys.argv[2]
    md = Mastodon(access_token=mdn_creds_filename)

    db_cursor.execute("SELECT post_id FROM games ORDER BY post_id;")
    post_ids = [int(row[0]) for row in db_cursor]
    for row_id, post_id in enumerate(post_ids):
        print(f"Deletion {row_id} / {len(post_ids)}: {post_id}")
        md.status_delete(post_id)
        time.sleep(1)
    db_cursor.execute("DROP TABLE games;")

    db_conn.commit()
    db_conn.close()


if __name__ == "__main__":
    main()