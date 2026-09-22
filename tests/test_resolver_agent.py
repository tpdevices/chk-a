"""Unit tests for the Resolver Agent (Loop 1).

DNS resolution is mocked so tests run offline and deterministically. Each test
patches ``dns.asyncresolver.Resolver`` with a shared AsyncMock whose ``.resolve``
is configured per scenario.
"""

from __future__ import annotations

import asyncio

from unittest.mock import AsyncMock, MagicMock, patch

import dns.exception
import dns.resolver
import pytest

from chk_a.agents.resolver_agent import ResolverAgent, ResolverHealth
from chk_a.models.schemas import CheckResult, ResolverConfig


class FakeRData:
    """Minimal stand-in for a dnspython A-record rdata (supports str())."""

    def __init__(self, ip: str) -> None:
        self._ip = ip

    def __str__(self) -> str:
        return self._ip


def _make_agent(resolvers, **kwargs) -> ResolverAgent:
    return ResolverAgent(resolvers, logger_name="test.resolver", **kwargs)


@pytest.fixture
def two_resolvers() -> list[ResolverConfig]:
    return [
        ResolverConfig(name="r1", address="8.8.8.8:53"),
        ResolverConfig(name="r2", address="1.1.1.1:53"),
    ]


# --------------------------------------------------------------------------- #
# ResolverHealth dataclass
# --------------------------------------------------------------------------- #
def test_health_record_success():
    h = ResolverHealth()
    h.record(100.0, True)
    assert h.success_rate == 1.0
    assert h.avg_latency_ms == 100.0
    assert h.total_queries == 1
    assert h.successful_queries == 1


def test_health_record_failure():
    h = ResolverHealth()
    h.record(50.0, False)
    # EMA with alpha=0.1: 1.0 -> 0.9*1.0 + 0.1*0.0 = 0.9
    assert h.success_rate == 0.9
    assert h.total_queries == 1
    assert h.successful_queries == 0


def test_health_ema_latency():
    h = ResolverHealth()
    h.record(100.0, True)
    h.record(200.0, True)
    # EMA with alpha=0.1: 100 -> 0.9*100 + 0.1*200 = 110
    assert abs(h.avg_latency_ms - 110.0) < 1e-6


def test_health_weight_factor_bounds():
    h = ResolverHealth()
    h.record(10.0, False)
    assert 0.0 <= h.weight_factor <= 1.0
    h.record(10.0, True)
    assert 0.0 <= h.weight_factor <= 1.0


# --------------------------------------------------------------------------- #
# Resolver construction / config parsing
# --------------------------------------------------------------------------- #
def test_build_resolver_parses_port_and_timeout():
    cfg = ResolverConfig(name="x", address="9.9.9.9:5353", timeout_ms=1500)
    agent = _make_agent([cfg])
    inst = agent._instances["x"]
    assert inst.nameservers == ["9.9.9.9"]
    assert inst.port == 5353
    assert inst.timeout == 1.5
    assert inst.lifetime == 1.5


def test_doh_resolver_is_marker():
    cfg = ResolverConfig(name="doh", address="https://dns.google/dns-query")
    agent = _make_agent([cfg])
    assert "doh" in agent._doh_names


def test_dot_resolver_is_marker():
    cfg = ResolverConfig(name="dot", address="tls://dns.google:853")
    agent = _make_agent([cfg])
    assert "dot" in agent._dot_names


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_check_fqdn_happy_path(two_resolvers):
    answer = [FakeRData("1.2.3.4"), FakeRData("5.6.7.8")]
    with patch("dns.asyncresolver.Resolver") as MockResolver:
        shared = AsyncMock()
        MockResolver.return_value = shared
        shared.resolve.return_value = answer
        agent = _make_agent(two_resolvers)
        results = await agent.check_fqdn("example.com")

    assert len(results) == 2
    for r in results:
        assert isinstance(r, CheckResult)
        assert r.success is True
        assert r.fqdn == "example.com"
        assert set(r.ips) == {"1.2.3.4", "5.6.7.8"}
        assert r.latency_ms >= 0.0
    # health updated for both resolvers
    assert agent.health["r1"].success_rate == 1.0
    assert agent.health["r2"].success_rate == 1.0


# --------------------------------------------------------------------------- #
# Error paths
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_check_fqdn_nxdomain(two_resolvers):
    with patch("dns.asyncresolver.Resolver") as MockResolver:
        shared = AsyncMock()
        MockResolver.return_value = shared
        shared.resolve.side_effect = dns.resolver.NXDOMAIN()
        agent = _make_agent(two_resolvers)
        results = await agent.check_fqdn("nope.invalid")

    assert len(results) == 2
    for r in results:
        assert r.success is False
        assert r.error == "NXDOMAIN"
        assert r.ips == []
    # EMA after one failure: 0.9
    assert agent.health["r1"].success_rate == 0.9


@pytest.mark.asyncio
async def test_check_fqdn_no_answer(two_resolvers):
    with patch("dns.asyncresolver.Resolver") as MockResolver:
        shared = AsyncMock()
        MockResolver.return_value = shared
        shared.resolve.side_effect = dns.resolver.NoAnswer()
        agent = _make_agent(two_resolvers)
        results = await agent.check_fqdn("empty.example.com")

    for r in results:
        assert r.success is False
        assert r.error == "NO_ANSWER"


@pytest.mark.asyncio
async def test_check_fqdn_no_nameservers(two_resolvers):
    with patch("dns.asyncresolver.Resolver") as MockResolver:
        shared = AsyncMock()
        MockResolver.return_value = shared
        shared.resolve.side_effect = dns.resolver.NoNameservers()
        agent = _make_agent(two_resolvers)
        results = await agent.check_fqdn("x.example.com")

    for r in results:
        assert r.success is False
        assert r.error == "NO_NAMESERVERS"


@pytest.mark.asyncio
async def test_check_fqdn_timeout(two_resolvers):
    with patch("dns.asyncresolver.Resolver") as MockResolver:
        shared = AsyncMock()
        MockResolver.return_value = shared
        shared.resolve.side_effect = dns.exception.Timeout()
        agent = _make_agent(two_resolvers)
        results = await agent.check_fqdn("slow.example.com")

    for r in results:
        assert r.success is False
        assert r.error == "TIMEOUT"


@pytest.mark.asyncio
async def test_check_fqdn_generic_dns_error(two_resolvers):
    with patch("dns.asyncresolver.Resolver") as MockResolver:
        shared = AsyncMock()
        MockResolver.return_value = shared
        shared.resolve.side_effect = dns.exception.DNSException("boom")
        agent = _make_agent(two_resolvers)
        results = await agent.check_fqdn("x.example.com")

    for r in results:
        assert r.success is False
        assert r.error.startswith("DNS_ERROR:")


@pytest.mark.asyncio
async def test_check_fqdn_unexpected_exception(two_resolvers):
    with patch("dns.asyncresolver.Resolver") as MockResolver:
        shared = AsyncMock()
        MockResolver.return_value = shared
        shared.resolve.side_effect = RuntimeError("weird")
        agent = _make_agent(two_resolvers)
        results = await agent.check_fqdn("x.example.com")

    for r in results:
        assert r.success is False
        assert r.error.startswith("UNEXPECTED:")


@ pytest.mark.asyncio
async def test_dot_resolver_resolves():
    """DoT resolvers query via dnspython DoTNameserver and return results."""
    cfg = [ResolverConfig(name="dot", address="tls://dns.google:853")]
    agent = _make_agent(cfg)

    # Build a mock response
    class MockRData:
        def __init__(self, ip: str) -> None:
            self._ip = ip
            self.rdtype = 1  # dns.rdatatype.A = 1
        def __str__(self) -> str:
            return self._ip

    class MockRRset:
        def __init__(self, ip: str):
            self._data = [MockRData(ip)]
        def __iter__(self):
            return iter(self._data)

    class MockResponse:
        def __init__(self):
            self.answer = [MockRRset("1.2.3.4")]

    mock_resp = MockResponse()

    # Mock the async_query method
    from unittest.mock import MagicMock
    mock_nameserver = MagicMock()
    mock_nameserver.async_query = AsyncMock(return_value=mock_resp)

    # Replace the nameserver directly (patching _build_dot_nameserver doesn't work
    # because it's called during __init__ before we can patch it)
    agent._dot_nameservers["dot"] = mock_nameserver

    results = await agent.check_fqdn("example.com")

    assert len(results) == 1
    assert results[0].success is True
    assert results[0].ips == ["1.2.3.4"]


@pytest.mark.asyncio
async def test_doh_resolver_resolves():
    """DoH resolvers query via HTTPS (DNS wireformat) and return results."""
    cfg = [ResolverConfig(name="doh", address="https://dns.google/dns-query")]
    agent = _make_agent(cfg)

    # Build a mock DNS wireformat response - use absolute names (trailing dot)
    query = dns.message.make_query("example.com.", dns.rdatatype.A)
    response = dns.message.make_response(query)
    response.answer.append(dns.rrset.from_text("example.com.", 300, "IN", "A", "1.2.3.4"))
    response_wire = response.to_wire()

    # Mock the _get_doh_session method to return our mock session
    from unittest.mock import MagicMock
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read = AsyncMock(return_value=response_wire)
    mock_resp.raise_for_status = MagicMock()
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(return_value=mock_resp)

    # Patch the method to return our mock session
    async def mock_get_doh_session(resolver_name):
        return mock_session

    agent._get_doh_session = mock_get_doh_session

    results = await agent.check_fqdn("example.com")

    assert len(results) == 1
    assert results[0].success is True
    assert results[0].ips == ["1.2.3.4"]


# --------------------------------------------------------------------------- #
# Concurrency
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_concurrency_limited_by_semaphore():
    resolvers = [ResolverConfig(name=f"r{i}", address=f"10.0.0.{i}:53") for i in range(6)]
    current = 0
    max_seen = 0
    lock = asyncio.Lock()

    async def fake_resolve(fqdn, rdtype="A"):
        nonlocal current, max_seen
        async with lock:
            current += 1
            max_seen = max(max_seen, current)
        await asyncio.sleep(0.02)
        async with lock:
            current -= 1
        return [FakeRData("1.1.1.1")]

    with patch("dns.asyncresolver.Resolver") as MockResolver:
        shared = AsyncMock()
        MockResolver.return_value = shared
        shared.resolve.side_effect = fake_resolve
        agent = _make_agent(resolvers, max_concurrent=2)
        results = await agent.check_fqdn("example.com")

    assert len(results) == 6
    assert max_seen <= 2  # semaphore must cap in-flight queries


@pytest.mark.asyncio
async def test_one_failing_resolver_does_not_block_others():
    resolvers = [
        ResolverConfig(name="good", address="8.8.8.8:53"),
        ResolverConfig(name="bad", address="1.1.1.1:53"),
    ]
    answer = [FakeRData("9.9.9.9")]

    def fake_build_resolver(self, cfg, default_timeout_ms=2000):
        inst = AsyncMock()
        if cfg.name == "good":
            inst.resolve.return_value = answer
        else:

            async def raise_nx(fqdn, rdtype="A"):
                raise dns.resolver.NXDOMAIN()

            inst.resolve.side_effect = raise_nx
        return inst

    with patch.object(ResolverAgent, "_build_resolver", fake_build_resolver):
        agent = _make_agent(resolvers)
        results = await agent.check_fqdn("example.com")

    by_name = {r.resolver: r for r in results}
    assert by_name["good"].success is True
    assert by_name["good"].ips == ["9.9.9.9"]
    assert by_name["bad"].success is False
    assert by_name["bad"].error == "NXDOMAIN"
