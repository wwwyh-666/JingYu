"""Offline tests must not contact model providers, even with a real local .env."""
import socket
import pytest


@pytest.fixture(autouse=True)
def forbid_external_network(monkeypatch):
    original=socket.getaddrinfo
    def local_only(host,*args,**kwargs):
        value=host.decode() if isinstance(host,bytes) else host
        if value not in {'localhost','127.0.0.1','::1',None}:
            raise AssertionError('External network is forbidden in offline tests')
        return original(host,*args,**kwargs)
    monkeypatch.setattr(socket,'getaddrinfo',local_only)
