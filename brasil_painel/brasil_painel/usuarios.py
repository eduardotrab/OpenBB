"""User store: a local JSON file with password hashes only (never plain text)."""

import json
import os
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

MIN_PASSWORD_LENGTH = 10


class UserStore:
    """Users of the dashboard, kept in a JSON file readable only by its owner."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()

    def _read(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, users: dict[str, dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(users, file, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def add(self, username: str, password: str) -> None:
        """Add a user; refuses duplicates and short passwords."""
        users = self._read()
        if username in users:
            raise ValueError(f"Usuário '{username}' já existe.")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"A senha precisa de pelo menos {MIN_PASSWORD_LENGTH} caracteres."
            )
        users[username] = {"hash": generate_password_hash(password)}
        self._write(users)

    def remove(self, username: str) -> None:
        """Remove a user; raises KeyError when missing."""
        users = self._read()
        del users[username]
        self._write(users)

    def list(self) -> list[str]:
        """Return the usernames, sorted."""
        return sorted(self._read())

    def exists(self, username: str) -> bool:
        """Whether the user exists."""
        return username in self._read()

    def verify(self, username: str, password: str) -> bool:
        """Check a password against the stored hash."""
        user = self._read().get(username)
        return bool(user) and check_password_hash(user["hash"], password)
