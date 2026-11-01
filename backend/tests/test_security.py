import pytest
from backend.security import is_safe_url, is_ip_blocked


def test_ssrf_blocked_localhost():
    safe, reason = is_safe_url("http://localhost:8000/api")
    assert not safe
    assert "SSRF" in reason or "blocked" in reason


def test_ssrf_blocked_loopback_ip():
    safe, reason = is_safe_url("http://127.0.0.1:5000")
    assert not safe
    assert "SSRF" in reason or "blocked" in reason


def test_ssrf_blocked_private_ips():
    assert is_ip_blocked("10.0.0.1")
    assert is_ip_blocked("192.168.1.100")
    assert is_ip_blocked("172.16.0.5")
    assert is_ip_blocked("127.0.0.1")
    assert is_ip_blocked("169.254.169.254")  # AWS/GCP metadata


def test_ssrf_blocked_cloud_metadata():
    safe, reason = is_safe_url("http://169.254.169.254/latest/meta-data/")
    assert not safe
    assert "SSRF" in reason or "blocked" in reason

    safe2, reason2 = is_safe_url("http://metadata.google.internal/computeMetadata/v1/")
    assert not safe2
    assert "blocked" in reason2


def test_unsafe_schemes_blocked():
    assert not is_safe_url("file:///etc/passwd")[0]
    assert not is_safe_url("ftp://example.com/data.txt")[0]
    assert not is_safe_url("gopher://example.com")[0]
    assert not is_safe_url("javascript:alert(1)")[0]


def test_valid_public_url():
    safe, reason = is_safe_url("https://www.wikipedia.org/wiki/Artificial_intelligence")
    assert safe
    assert reason == ""
