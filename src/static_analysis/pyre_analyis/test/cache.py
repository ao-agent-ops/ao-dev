import sqlite3
from threading import Lock
import tomllib
import typing as t
import os
import json
import pickle
import zlib


class Cache:
    def __init__(self):
        config = tomllib.load(open("configs/main.toml", "rb"))
        working_stage = config["working_stage"]
        cache_dir = f"{working_stage}/prompt_cache"
        os.makedirs(cache_dir, exist_ok=True)
        parallelism = 8
        self.db_locks = [Lock() for _ in range(parallelism)]
        db_files = [f"{cache_dir}/cache_{i}.db" for i in range(parallelism)]
        with open("configs/schemas/cache.sql", "r") as f:
            schema = f.read()
        self.dbs = []
        for db_file in db_files:
            # print(f"Opening {db_file}")
            db = sqlite3.connect(db_file, check_same_thread=False)
            cur = db.cursor()
            cur.executescript(schema)
            db.commit()
            self.dbs.append(db)

    def _get_db(self, key: str) -> t.Tuple[sqlite3.Connection, Lock]:
        idx = zlib.adler32(key.encode()) % len(self.dbs)
        return self.dbs[idx], self.db_locks[idx]

    def get_prompt(self, key: str, prompt: str) -> t.Optional[t.Any]:
        db, db_lock = self._get_db(key)
        with db_lock:
            cur = db.cursor()
            cur.execute("SELECT prompt, value FROM prompt_cache WHERE key = ?", (key,))
            result = cur.fetchone()
            if result is not None:
                stored_prompt, value = result
                # NOTE: could check this with the db, but that makes debugging bad caching harder.
                if stored_prompt == prompt:
                    return json.loads(value)
                return None
            return None

    def set_prompt(self, key: str, prompt: str, value: t.Any):
        value = json.dumps(value)
        db, db_lock = self._get_db(key)
        with db_lock:
            cur = db.cursor()
            cur.execute(
                "REPLACE INTO prompt_cache (key, prompt, value) VALUES (?, ?, ?)",
                (key, prompt, value),
            )
            db.commit()

    def get_object(self, key: str) -> t.Any:
        db, db_lock = self._get_db(key)
        with db_lock:
            cur = db.cursor()
            cur.execute("SELECT value FROM object_cache WHERE key = ?", (key,))
            result = cur.fetchone()
            if result is not None:
                return pickle.loads(result[0])
            return None

    def set_object(self, key: str, value: t.Any):
        value = pickle.dumps(value)
        db, db_lock = self._get_db(key)
        with db_lock:
            cur = db.cursor()
            cur.execute("REPLACE INTO object_cache (key, value) VALUES (?, ?)", (key, value))
            db.commit()

    def clear_objects(self, prefix: str):
        db, db_lock = self._get_db(prefix)
        with db_lock:
            cur = db.cursor()
            cur.execute("DELETE FROM object_cache WHERE key LIKE ?", (prefix + "%",))
            db.commit()


CACHE = Cache()
