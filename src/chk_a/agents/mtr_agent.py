"""MTR Agent — server-side continuous network path monitoring with statistical aggregation.

Runs mtr to configured resolvers and produces structured output with loss%,
avg/max latency per hop suitable for visualization (JSON) and human-readable display.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import shutil
import socket
import subprocess
from dataclasses import dataclass
from typing import Any

from ..models.schemas import ResolverConfig
from ..utils.logger import setup_logger


@dataclass
class MTRHop:
    """A single hop in the MTR path with statistical aggregation."""

    hop_num: int
    host: str
    loss_pct: float
    sent: int
    last_ms: float
    avg_ms: float
    best_ms: float
    worst_ms: float
    stdev_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "hop_num": self.hop_num,
            "host": self.host,
            "loss_pct": self.loss_pct,
            "sent": self.sent,
            "last_ms": self.last_ms,
            "avg_ms": self.avg_ms,
            "best_ms": self.best_ms,
            "worst_ms": self.worst_ms,
            "stdev_ms": self.stdev_ms,
        }


@dataclass
class MTRResult:
    """Complete MTR result for one resolver with aggregated statistics."""

    resolver_name: str
    target_ip: str
    target_hostname: str | None = None
    hops: list[MTRHop] = None
    success: bool = True
    error: str | None = None
    command: str = ""
    src: str = ""
    tests: int = 0

    def __post_init__(self) -> None:
        if self.hops is None:
            self.hops = []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "resolver_name": self.resolver_name,
            "target_ip": self.target_ip,
            "target_hostname": self.target_hostname,
            "hops": [hop.to_dict() for hop in self.hops],
            "success": self.success,
            "error": self.error,
            "command": self.command,
            "src": self.src,
            "tests": self.tests,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


class MTRAgent:
    """Runs MTR to resolvers for continuous path monitoring with statistics."""

    # SEC-012: Hard concurrency ceiling for MTR runs
    MAX_CONCURRENT_MTR = 4

    def __init__(
        self,
        resolvers: list[ResolverConfig],
        logger_name: str = "chk_a.mtr",
        timeout_sec: int = 10,
        max_hops: int = 30,
        count: int = 10,
        interval_ms: int = 1000,
        mode: str = "icmp",
        port: int | None = None,
    ) -> None:
        self.resolvers: dict[str, ResolverConfig] = {r.name: r for r in resolvers}
        self.timeout_sec = timeout_sec
        self.max_hops = max_hops
        self.count = count
        self.interval_ms = interval_ms
        self.mode = mode  # "icmp", "tcp", "udp"
        self.port = port
        self.logger = setup_logger(logger_name)

        # Find mtr binary
        self._mtr_bin = shutil.which("mtr")
        if not self._mtr_bin:
            self.logger.warning("mtr binary not found in PATH; MTR will fail")

        # SEC-012: Semaphore to limit concurrent MTR subprocesses
        self._mtr_semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_MTR)

    def _validate_target_ip(self, target: str) -> bool:
        """Validate that target is a valid IP address (IPv4 or IPv6).

        Returns True if valid, False otherwise.
        """
        try:
            ipaddress.ip_address(target)
            return True
        except ValueError:
            return False

    def _parse_resolver_address(self, address: str) -> tuple[str, str | None]:
        """Parse resolver address into (ip, hostname)."""
        # Handle "IP:port" format
        if ":" in address and not address.startswith(("http://", "https://")):
            host, port_str = address.rsplit(":", 1)
            try:
                int(port_str)  # validate it's a port
                return host, None
            except ValueError:
                return address, None
        return address, None

    def _resolve_hostname(self, target: str) -> tuple[str, str | None]:
        """Resolve hostname to IP address if needed.

        Returns (ip, original_hostname_or_None).
        If target is already an IP, returns (target, None).
        """
        # Check if it's already an IP address (IPv4)
        try:
            socket.inet_aton(target)
            return target, None
        except OSError:
            pass

        # Try to resolve hostname
        try:
            ip = socket.gethostbyname(target)
            return ip, target
        except socket.gaierror as exc:
            self.logger.warning("Failed to resolve hostname '%s': %s", target, exc)
            return target, target  # Return original, will fail in mtr

    def _build_command(self, resolver: ResolverConfig, target_ip: str | None = None, resolve_hostnames: bool = True, mode: str | None = None, port: int | None = None) -> list[str]:
        """Build MTR command for a resolver in JSON report mode.

        Args:
            resolver: ResolverConfig object
            target_ip: Target IP address (resolved from hostname if needed)
            resolve_hostnames: If True, allow mtr to resolve hop hostnames (no -n flag).
                               If False, use -n flag for faster execution (IP-only output).
                               Default True so CLI hostname targets work correctly.
            mode: Override MTR probe mode ("icmp", "tcp", "udp"). Defaults to self.mode.
            port: Destination port for TCP/UDP mode. Defaults to self.port.
        """
        if target_ip is None:
            target_ip, _ = self._parse_resolver_address(resolver.address)

        # Determine mode and port
        effective_mode = mode or self.mode
        effective_port = port if port is not None else self.port

        cmd = [
            self._mtr_bin,
            "-j",  # JSON output
            # "-r" removed: report mode outputs text, not JSON
            "-c",
            str(self.count),  # Number of pings per hop
            "-i",
            str(self.interval_ms / 1000.0),  # Interval in seconds (float)
            "-Z",
            str(self.timeout_sec),  # Timeout per ping (use -Z not -W)
            "-m",
            str(self.max_hops),  # Max hops
        ]

        # Add TCP/UDP mode flags
        if effective_mode == "tcp":
            cmd.extend(["-T"])
            if effective_port:
                cmd.extend(["-P", str(effective_port)])
        elif effective_mode == "udp":
            cmd.extend(["-u"])  # lowercase -u for UDP (uppercase -U is --max-unknown)
            if effective_port:
                cmd.extend(["-P", str(effective_port)])
        # ICMP mode (default) - no extra flags needed

        if not resolve_hostnames:
            cmd.append("-n")  # Don't resolve hostnames (faster, IP-only output)
        cmd.append(target_ip)
        return cmd

    def _parse_json_output(self, output: str) -> tuple[list[MTRHop], str, int]:
        """Parse MTR JSON output into MTRHop objects.

        Returns tuple of (hops, src, tests).
        """
        hops = []
        src = ""
        tests = 0

        try:
            data = json.loads(output)
            report = data.get("report", {})
            mtr_info = report.get("mtr", {})
            hubs = report.get("hubs", [])

            src = mtr_info.get("src", "")
            tests = mtr_info.get("tests", 0)

            for hub in hubs:
                hop = MTRHop(
                    hop_num=hub.get("count", 0),
                    host=hub.get("host", ""),
                    loss_pct=float(hub.get("Loss%", 0.0)),
                    sent=int(hub.get("Snt", 0)),
                    last_ms=float(hub.get("Last", 0.0)),
                    avg_ms=float(hub.get("Avg", 0.0)),
                    best_ms=float(hub.get("Best", 0.0)),
                    worst_ms=float(hub.get("Wrst", 0.0)),
                    stdev_ms=float(hub.get("StDev", 0.0)),
                )
                hops.append(hop)

        except json.JSONDecodeError as exc:
            self.logger.error("Failed to parse MTR JSON output: %s", exc)
        except Exception as exc:  # noqa: BLE001
            self.logger.error("Unexpected error parsing MTR output: %s", exc)

        return hops, src, tests

    async def trace_resolver(self, resolver_name: str, resolve_hostnames: bool = True, mode: str | None = None, port: int | None = None) -> MTRResult:
        """Run MTR to a single resolver.

        Args:
            resolver_name: Name of the resolver to trace
            resolve_hostnames: If True, allow mtr to resolve hop hostnames (no -n flag).
                              If False, use -n flag for faster execution (IP-only output).
                              Default True so CLI hostname targets work correctly.
            mode: Override MTR probe mode ("icmp", "tcp", "udp").
            port: Destination port for TCP/UDP mode.
        """
        resolver = self.resolvers.get(resolver_name)
        if not resolver:
            return MTRResult(
                resolver_name=resolver_name,
                target_ip="",
                success=False,
                error=f"Resolver '{resolver_name}' not found",
            )

        # Parse address from resolver config
        target_ip, _ = self._parse_resolver_address(resolver.address)

        # Extract port from resolver address for TCP/UDP mode
        # Format: "IP:port" or "hostname:port"
        resolver_port = None
        if ":" in resolver.address and not resolver.address.startswith(("http://", "https://")):
            try:
                _, port_str = resolver.address.rsplit(":", 1)
                resolver_port = int(port_str)
            except (ValueError, IndexError):
                pass

        # Determine effective mode and port (priority: explicit args > resolver config > agent defaults)
        effective_mode = mode or self.mode
        effective_port = port if port is not None else (resolver_port if resolver_port is not None else self.port)

        # Resolve hostname to IP if needed (for CLI usage where target might be hostname)
        resolved_ip, original_hostname = self._resolve_hostname(target_ip)

        # Build command string early for error reporting (before validation)
        cmd = self._build_command(resolver, resolved_ip, resolve_hostnames=False, mode=effective_mode, port=effective_port)
        cmd_str = " ".join(cmd)

        # SEC-001: Validate target IP before passing to subprocess (command injection prevention)
        if not self._validate_target_ip(resolved_ip):
            return MTRResult(
                resolver_name=resolver_name,
                target_ip=resolved_ip,
                target_hostname=original_hostname,
                success=False,
                error=f"Invalid target IP address: {resolved_ip}",
                command=cmd_str,
            )

        if not self._mtr_bin:
            return MTRResult(
                resolver_name=resolver_name,
                target_ip=resolved_ip,
                target_hostname=original_hostname,
                success=False,
                error="mtr binary not available",
                command=cmd_str,
            )

        self.logger.info("Running MTR to %s (%s) mode=%s port=%s", resolver_name, resolved_ip, effective_mode, effective_port)

        # Correct timeout: max_hops * count * timeout_sec + buffer
        # MTR sends 'count' pings per hop, each with 'timeout_sec' timeout
        max_duration = self.max_hops * self.count * self.timeout_sec + 60

        try:
            # Run in thread pool since subprocess is blocking
            loop = asyncio.get_running_loop()
            proc = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=max_duration,
                ),
            )

            if proc.returncode != 0:
                return MTRResult(
                    resolver_name=resolver_name,
                    target_ip=resolved_ip,
                    target_hostname=original_hostname,
                    success=False,
                    error=f"mtr exited with code {proc.returncode}: {proc.stderr}",
                    command=cmd_str,
                )

            hops, src, tests = self._parse_json_output(proc.stdout)
            return MTRResult(
                resolver_name=resolver_name,
                target_ip=resolved_ip,
                target_hostname=original_hostname,
                hops=hops,
                success=True,
                command=cmd_str,
                src=src,
                tests=tests,
            )

        except subprocess.TimeoutExpired:
            return MTRResult(
                resolver_name=resolver_name,
                target_ip=resolved_ip,
                success=False,
                error=f"Timeout after {max_duration}s",
                command=cmd_str,
            )
        except Exception as exc:  # noqa: BLE001
            return MTRResult(
                resolver_name=resolver_name,
                target_ip=resolved_ip,
                success=False,
                error=f"Unexpected error: {exc}",
                command=cmd_str,
            )

    async def trace_all(self, resolve_hostnames: bool = True, mode: str | None = None, port: int | None = None) -> list[MTRResult]:
        """Run MTR to all configured resolvers.

        Args:
            resolve_hostnames: Ignored (kept for API compatibility). Target hostname
                              resolution is always performed internally; mtr is run
                              with -n flag (IP-only output) for performance.
            mode: Override MTR probe mode for all resolvers ("icmp", "tcp", "udp").
            port: Destination port for TCP/UDP mode for all resolvers.
        """
        # SEC-012: Use semaphore to limit concurrent MTR subprocesses
        async def _trace_with_semaphore(name: str) -> MTRResult:
            async with self._mtr_semaphore:
                return await self.trace_resolver(name, resolve_hostnames=False, mode=mode, port=port)

        tasks = [_trace_with_semaphore(name) for name in self.resolvers]
        return await asyncio.gather(*tasks)

    def print_results(self, results: list[MTRResult], json_output: bool = False) -> None:
        """Print MTR results to stdout."""
        if json_output:
            print(json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False))
            return

        for result in results:
            print(f"\n=== MTR to {result.resolver_name} ({result.target_ip}) ===")
            print(f"Command: {result.command}")
            if result.src:
                print(f"Source: {result.src} | Tests: {result.tests}")
            if not result.success:
                print(f"ERROR: {result.error}")
                continue

            if not result.hops:
                print("  No hops recorded")
                continue

            # Header
            header = (
                f"  {'Hop':>3}  {'Host':<20}  {'Loss%':>6}  {'Snt':>4}  "
                f"{'Last':>7}  {'Avg':>7}  {'Best':>7}  {'Wrst':>7}  {'StDev':>7}"
            )
            print(header)
            sep = (
                f"  {'-'*3}  {'-'*20}  {'-'*6}  {'-'*4}  "
                f"{'-'*7}  {'-'*7}  {'-'*7}  {'-'*7}  {'-'*7}"
            )
            print(sep)

            for hop in result.hops:
                line = (
                    f"  {hop.hop_num:3d}  {hop.host:<20}  {hop.loss_pct:5.1f}%  {hop.sent:4d}  "
                    f"{hop.last_ms:7.2f}  {hop.avg_ms:7.2f}  {hop.best_ms:7.2f}  "
                    f"{hop.worst_ms:7.2f}  {hop.stdev_ms:7.2f}"
                )
                print(line)


__all__ = ["MTRAgent", "MTRResult", "MTRHop"]
