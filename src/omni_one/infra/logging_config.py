"""Compat shim — infra.logging_config. Tries core, else minimal stdlib fallback."""
try:
    from ..core.logging_config import *  # type: ignore
    from ..core.logging_config import (  # type: ignore
        configure_logging, get_logger, RequestContext, OperationTimer,
        set_request_context, clear_request_context, get_request_context,
        request_id_var, user_id_var,
    )
except Exception:
    try:
        from core.logging_config import *  # type: ignore
        from core.logging_config import (  # type: ignore
            configure_logging, get_logger, RequestContext, OperationTimer,
            set_request_context, clear_request_context, get_request_context,
            request_id_var, user_id_var,
        )
    except Exception:
        import logging as _logging
        import time as _time
        import contextvars as _cv
        _request_id_var = _cv.ContextVar("request_id", default=None)
        _user_id_var = _cv.ContextVar("user_id", default=None)
        _session_id_var = _cv.ContextVar("session_id", default=None)
        _trace_id_var = _cv.ContextVar("trace_id", default=None)
        request_id_var = _request_id_var  # type: ignore
        user_id_var = _user_id_var  # type: ignore
        session_id_var = _session_id_var  # type: ignore
        trace_id_var = _trace_id_var  # type: ignore

        def configure_logging(*a, **kw):
            _logging.basicConfig(level=_logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
            return _logging.getLogger()

        class _FallbackLogger:
            def __init__(self, name):
                self._log = _logging.getLogger(name)
            def _fmt(self, msg, kwargs):
                if kwargs:
                    extra = " ".join(f"{k}={v}" for k, v in kwargs.items())
                    return f"{msg} {extra}"
                return msg
            def info(self, msg, *a, **kw):
                self._log.info(self._fmt(msg, kw))
            def warning(self, msg, *a, **kw):
                self._log.warning(self._fmt(msg, kw))
            def error(self, msg, *a, **kw):
                self._log.error(self._fmt(msg, kw))
            def debug(self, msg, *a, **kw):
                self._log.debug(self._fmt(msg, kw))
            def exception(self, msg, *a, **kw):
                self._log.exception(self._fmt(msg, kw))
            def log(self, level, msg, *a, **kw):
                if isinstance(level, str):
                    level = {"debug": 10, "info": 20, "warning": 30, "error": 40, "critical": 50}.get(level.lower(), 20)
                self._log.log(level, self._fmt(msg, kw))

        def get_logger(name=__name__):
            return _FallbackLogger(name)

        def set_request_context(request_id=None, user_id=None, session_id=None, trace_id=None, **kw):
            if request_id is not None:
                _request_id_var.set(request_id)
            if user_id is not None:
                _user_id_var.set(user_id)
            if session_id is not None:
                _session_id_var.set(session_id)
            if trace_id is not None:
                _trace_id_var.set(trace_id)

        def clear_request_context():
            try:
                _request_id_var.set(None)
                _user_id_var.set(None)
                _session_id_var.set(None)
                _trace_id_var.set(None)
            except Exception:
                pass

        def get_request_context():
            return {
                "request_id": _request_id_var.get(),
                "user_id": _user_id_var.get(),
                "session_id": _session_id_var.get(),
                "trace_id": _trace_id_var.get(),
            }

        class RequestContext:
            def __init__(self, request_id=None, user_id=None, session_id=None, trace_id=None, **kw):
                self.request_id = request_id
                self.user_id = user_id
                self.session_id = session_id
                self.trace_id = trace_id
                self.tokens = []
            def __enter__(self):
                self.tokens.append(_request_id_var.set(self.request_id))
                self.tokens.append(_user_id_var.set(self.user_id))
                self.tokens.append(_session_id_var.set(self.session_id))
                self.tokens.append(_trace_id_var.set(self.trace_id))
                return self
            def __exit__(self, *a):
                for t in reversed(self.tokens):
                    try:
                        t.var.set(None)
                    except Exception:
                        pass
                return False

        class OperationTimer:
            def __init__(self, name, logger=None):
                self.name = name
                self.logger = logger or get_logger()
                self.start = None
                self.duration_ms = None
            def __enter__(self):
                self.start = _time.time()
                return self
            def __exit__(self, *a):
                if self.start is not None:
                    self.duration_ms = (_time.time() - self.start) * 1000
                else:
                    self.duration_ms = 0
                try:
                    if self.logger:
                        self.logger.info(f"operation_completed operation={self.name} duration_ms={round(self.duration_ms or 0,2)}")
                except Exception:
                    pass
                return False
