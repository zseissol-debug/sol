"""一个对象一个 json 文件的极简存储。原子写入，路径安全。"""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Generic, Iterator, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
_SAFE_ID = re.compile(r"^[\w.\-]{1,128}$")


class InvalidId(ValueError):
    pass


class JsonDir(Generic[T]):
    def __init__(self, base: Path, model: type[T]):
        self.base = base
        self.model = model
        self._lock = threading.RLock()
        self.base.mkdir(parents=True, exist_ok=True)

    def _path(self, obj_id: str) -> Path:
        if not _SAFE_ID.match(obj_id):
            raise InvalidId(f"非法 id: {obj_id!r}")
        return self.base / f"{obj_id}.json"

    def get(self, obj_id: str) -> T | None:
        path = self._path(obj_id)
        with self._lock:
            if not path.is_file():
                return None
            return self.model.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, obj: T) -> T:
        path = self._path(getattr(obj, "id"))
        payload = obj.model_dump_json(indent=2)
        with self._lock:
            fd, tmp = tempfile.mkstemp(dir=self.base, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(payload)
                os.replace(tmp, path)
            except BaseException:
                if os.path.exists(tmp):
                    os.unlink(tmp)
                raise
        return obj

    def delete(self, obj_id: str) -> bool:
        path = self._path(obj_id)
        with self._lock:
            if path.is_file():
                path.unlink()
                return True
            return False

    def all(self) -> list[T]:
        out: list[T] = []
        with self._lock:
            for path in sorted(self.base.glob("*.json")):
                try:
                    out.append(self.model.model_validate_json(path.read_text(encoding="utf-8")))
                except Exception:  # 坏文件不拖垮整个列表
                    continue
        return out

    def __iter__(self) -> Iterator[T]:
        return iter(self.all())
