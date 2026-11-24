"""The default transport: which connection errors occur before the send."""

from __future__ import annotations

import socket
import urllib.error
from typing import Any

import pytest

from feedbackpilgrim import APIConnectionError, APITimeoutError, Request, UrllibTransport

REQUEST = Request("POST", "https://feedback.example.com/api/public/v1/posts", {}, b"{}")


class FailingOpener:
    def __init__(self, error: BaseException) -> None:
        self.error = error

    def open(self, *args: Any, **kwargs: Any) -> Any:
        raise self.error


def send_with(error: BaseException) -> APIConnectionError:
    transport = UrllibTransport()
    transport._opener = FailingOpener(error)  # type: ignore[assignment]
    with pytest.raises(APIConnectionError) as caught:
        transport(REQUEST, 30)
    return caught.value


@pytest.mark.parametrize(
    "reason",
    [
        socket.gaierror(-2, "Name or service not known"),
        ConnectionRefusedError(111, "Connection refused"),
        TimeoutError("timed out"),
    ],
    ids=["dns failure", "refused connection", "connect timeout"],
)
def test_an_error_before_the_send(reason: OSError) -> None:
    assert send_with(urllib.error.URLError(reason)).before_send is True


def test_a_connect_timeout_is_a_timeout_error() -> None:
    assert isinstance(send_with(urllib.error.URLError(TimeoutError("timed out"))), APITimeoutError)


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.URLError(ConnectionResetError(104, "Connection reset by peer")),
        urllib.error.URLError(OSError(113, "No route to host")),
        TimeoutError("The read operation timed out"),
        ConnectionResetError(104, "Connection reset by peer"),
    ],
    ids=["reset while it sends", "unreachable host", "read timeout", "reset after the send"],
)
def test_another_connection_error(error: BaseException) -> None:
    assert send_with(error).before_send is False
