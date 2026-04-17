from contextlib import contextmanager
import time
from typing import Callable, TypeVar

import requests


T = TypeVar("T")


@contextmanager
def no_proxy_requests_session():
    """
    AKShare 在当前环境中会错误地走到系统代理，导致东财接口请求失败。
    这里临时替换 requests.Session，强制 trust_env=False。
    """

    original_session = requests.Session
    original_session_cls = requests.sessions.Session

    class NoProxySession(original_session_cls):  # type: ignore[misc, valid-type]
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.trust_env = False

    requests.Session = NoProxySession
    requests.sessions.Session = NoProxySession
    try:
        yield
    finally:
        requests.Session = original_session
        requests.sessions.Session = original_session_cls


def run_without_proxy(
    func: Callable[..., T],
    *args,
    retries: int = 3,
    retry_delay: float = 1.2,
    **kwargs,
) -> T:
    last_exception = None
    for attempt in range(retries):
        try:
            with no_proxy_requests_session():
                return func(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - network retry path
            last_exception = exc
            if attempt == retries - 1:
                raise
            time.sleep(retry_delay * (attempt + 1))
    raise last_exception
