from kcos.operator_auth import is_loopback_host, operator_authorized


def test_local_operator_transport_is_frictionless():
    assert is_loopback_host("127.0.0.1:8080")
    assert is_loopback_host("localhost:8080")
    assert is_loopback_host("[::1]:8080")
    assert operator_authorized("127.0.0.1:8080", None, "secret", True)


def test_remote_operator_transport_requires_token():
    assert not operator_authorized("kcos.example.com", None, "secret", True)
    assert not operator_authorized("kcos.example.com", "wrong", "secret", True)
    assert operator_authorized("kcos.example.com", "secret", "secret", True)
