from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from logging import INFO, ERROR, WARNING, DEBUG, getLogger, StreamHandler, Formatter
from typing import Any


class LogEntry:
    def __init__(
        self,
        level: str,
        message: str,
        project_id: str = '',
        stage_id: str = '',
        trace_id: str = '',
        error: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.timestamp: datetime = datetime.now(timezone.utc)
        self.level: str = level
        self.message: str = message
        self.project_id: str = project_id
        self.stage_id: str = stage_id
        self.trace_id: str = trace_id
        self.error: str | None = error
        self.extra: dict[str, Any] = extra or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'level': self.level,
            'message': self.message,
            'project_id': self.project_id,
            'stage_id': self.stage_id,
            'trace_id': self.trace_id,
            'error': self.error,
            **self.extra,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


LEVEL_MAP = {
    'DEBUG': DEBUG,
    'INFO': INFO,
    'WARNING': WARNING,
    'ERROR': ERROR,
}


class StructuredLogger:
    """Structured logger that keeps an in-memory ring buffer and bridges to Python logging."""

    def __init__(self, max_entries: int = 1000, json_output: bool = True) -> None:
        self._logs: list[LogEntry] = []
        self._max_entries = max_entries
        self._json_output = json_output
        self._setup_std_logger()

    def _setup_std_logger(self) -> None:
        self._std_logger = getLogger('smartvideo')
        if not self._std_logger.handlers:
            handler = StreamHandler(sys.stdout)
            formatter = Formatter('%(asctime)s [%(levelname)s] %(message)s')
            handler.setFormatter(formatter)
            self._std_logger.addHandler(handler)
            self._std_logger.setLevel(INFO)

    def _add(self, entry: LogEntry) -> None:
        self._logs.append(entry)
        if len(self._logs) > self._max_entries:
            self._logs.pop(0)
        level_no = LEVEL_MAP.get(entry.level, INFO)
        if self._json_output:
            self._std_logger.log(level_no, entry.to_json())
        else:
            self._std_logger.log(level_no, '[%s] [%s] %s', entry.project_id, entry.stage_id, entry.message)

    def debug(self, project_id: str, stage_id: str, message: str, trace_id: str = '', **extra: Any) -> None:
        self._add(LogEntry('DEBUG', message, project_id, stage_id, trace_id, extra=extra))

    def info(self, project_id: str, stage_id: str, message: str, trace_id: str = '', **extra: Any) -> None:
        self._add(LogEntry('INFO', message, project_id, stage_id, trace_id, extra=extra))

    def warning(self, project_id: str, stage_id: str, message: str, trace_id: str = '', **extra: Any) -> None:
        self._add(LogEntry('WARNING', message, project_id, stage_id, trace_id, extra=extra))

    def error(self, project_id: str, stage_id: str, message: str, trace_id: str = '', error: str | None = None, **extra: Any) -> None:
        self._add(LogEntry('ERROR', message, project_id, stage_id, trace_id, error=error, extra=extra))

    def get_logs(self, level: str | None = None, project_id: str | None = None,
                 trace_id: str | None = None, limit: int = 100) -> list[LogEntry]:
        logs = list(self._logs)
        if level:
            logs = [l for l in logs if l.level == level]
        if project_id:
            logs = [l for l in logs if l.project_id == project_id]
        if trace_id:
            logs = [l for l in logs if l.trace_id == trace_id]
        return logs[-limit:]

    def export(self) -> list[dict[str, Any]]:
        return [l.to_dict() for l in self._logs]

    def clear(self) -> None:
        self._logs.clear()


_logger = StructuredLogger()


def get_logger() -> StructuredLogger:
    return _logger
