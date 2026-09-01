"""Traceroute Agent — server-side path visualization for DNS resolver education.

Runs traceroute to configured resolvers and produces structured output
suitable for visualization (JSON) and human-readable display.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..models.schemas import ResolverConfig
from ..utils.logger import setup_logger


@dataclass
class Hop:
    """A single hop in the traceroute path."""

    ttl: int
    ip: str | None = None
    hostname: str | None = None
    rtt_ms: float | None = None
    rtt_ms_list: list[float] = None

    def __post_init__(self) -> None:
        if self.rtt_ms_list is None:
            self.rtt_ms_list = []


@dataclass
class TracerouteResult:
    """Complete traceroute result for one resolver."""

    resolver_name: str
    target_ip: str
    target_hostname: str | None = None
    hops: list[Hop] = None
    success: bool = True
    error: str | None = None
    command: str = ""

    def __post_init__(self) -> None:
        if self.hops is None:
            self.hops = []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "resolver_name": self.resolver_name,
            "target_ip": self.target_ip,
            "target_hostname": self.target_hostname,
            "hops": [
                {
                    "ttl": hop.ttl,
                    "ip": hop.ip,
                    "hostname": hop.hostname,
                    "rtt_ms": hop.rtt_ms,
                    "rtt_ms_list": hop.rtt_ms_list,
                }
                for hop in self.hops
            ],
            "success": self.success,
            "error": self.error,
            "command": self.command,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


class TracerouteAgent:
    """Runs traceroute to resolvers for path visualization."""

    def __init__(
        self,
        resolvers: list[ResolverConfig],
        logger_name: str = "chk_a.traceroute",
        timeout_sec: int = 30,
        max_hops: int = 30,
        method: str = "I",  # I=ICMP, T=TCP, U=UDP
        queries_per_hop: int = 3,
    ) -> None:
        self.resolvers: dict[str, ResolverConfig] = {r.name: r for r in resolvers}
        self.timeout_sec = timeout_sec
        self.max_hops = max_hops
        self.method = method
        self.queries_per_hop = queries_per_hop
        self.logger = setup_logger(logger_name)

        # Find traceroute binary
        self._traceroute_bin = shutil.which("traceroute")
        if not self._traceroute_bin:
            self.logger.warning("traceroute binary not found in PATH; traceroute will fail")

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

    def _build_command(self, resolver: ResolverConfig) -> list[str]:
        """Build traceroute command for a resolver."""
        target_ip, _ = self._parse_resolver_address(resolver.address)

        cmd = [
            self._traceroute_bin,
            "-n",  # Don't resolve hostnames (faster)
            "-m", str(self.max_hops),
            "-q", str(self.queries_per_hop),
            "-w", str(self.timeout_sec),
        ]

        # Add method flag
        if self.method == "I":
            cmd.append("-I")
        elif self.method == "T":
            cmd.append("-T")
        elif self.method == "U":
            cmd.append("-U")

        cmd.append(target_ip)
        return cmd

    def _parse_output(self, output: str) -> list[Hop]:
        """Parse traceroute output into Hop objects."""
        hops = []
        # Regex to match traceroute output lines
        # Format: " 1  192.168.1.1  1.234 ms  1.123 ms  1.456 ms"
        # Or: " 1  * * *"
        # Or: " 1  192.168.1.1  1.234 ms  *  1.456 ms"
        line_re = re.compile(
            r"^\s*(\d+)\s+"  # hop number (TTL)
            r"(?:(\d{1,3}(?:\.\d{1,3}){3})|(\*))\s+"  # IP or *
            r"(?:(\d+\.?\d*)\s*ms\s*)?"  # RTT 1
            r"(?:(\d+\.?\d*)\s*ms\s*)?"  # RTT 2
            r"(?:(\d+\.?\d*)\s*ms\s*)?"  # RTT 3
        )

        for line in output.splitlines():
            line = line.strip()
            if not line or line.startswith("traceroute to"):
                continue

            match = line_re.match(line)
            if not match:
                continue

            ttl = int(match.group(1))
            ip = match.group(2) if match.group(2) != "*" else None
            # If IP is *, hostname would be unresolvable anyway
            hostname = None
            if ip and self.method != "n":
                # Could resolve here but -n flag makes it faster
                pass

            rtt_list = []
            for i in range(3, 6):
                val = match.group(i)
                if val:
                    try:
                        rtt_list.append(float(val))
                    except ValueError:
                        pass

            rtt_ms = sum(rtt_list) / len(rtt_list) if rtt_list else None

            hop = Hop(
                ttl=ttl,
                ip=ip,
                hostname=hostname,
                rtt_ms=rtt_ms,
                rtt_ms_list=rtt_list,
            )
            hops.append(hop)

        return hops

    async def trace_resolver(self, resolver_name: str) -> TracerouteResult:
        """Run traceroute to a single resolver."""
        resolver = self.resolvers.get(resolver_name)
        if not resolver:
            return TracerouteResult(
                resolver_name=resolver_name,
                target_ip="",
                success=False,
                error=f"Resolver '{resolver_name}' not found",
            )

        target_ip, _ = self._parse_resolver_address(resolver.address)
        cmd = self._build_command(resolver)
        cmd_str = " ".join(cmd)

        if not self._traceroute_bin:
            return TracerouteResult(
                resolver_name=resolver_name,
                target_ip=target_ip,
                success=False,
                error="traceroute binary not available",
                command=cmd_str,
            )

        self.logger.info("Running traceroute to %s (%s)", resolver_name, target_ip)

        try:
            # Run in thread pool since subprocess is blocking
            loop = asyncio.get_running_loop()
            proc = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_sec + 5,
                ),
            )

            if proc.returncode != 0 and proc.returncode != 1:
                # returncode 1 = some hops unreachable (normal for traceroute)
                return TracerouteResult(
                    resolver_name=resolver_name,
                    target_ip=target_ip,
                    success=False,
                    error=f"traceroute exited with code {proc.returncode}: {proc.stderr}",
                    command=cmd_str,
                )

            hops = self._parse_output(proc.stdout)
            return TracerouteResult(
                resolver_name=resolver_name,
                target_ip=target_ip,
                hops=hops,
                success=True,
                command=cmd_str,
            )

        except subprocess.TimeoutExpired:
            return TracerouteResult(
                resolver_name=resolver_name,
                target_ip=target_ip,
                success=False,
                error=f"Timeout after {self.timeout_sec + 5}s",
                command=cmd_str,
            )
        except Exception as exc:  # noqa: BLE001
            return TracerouteResult(
                resolver_name=resolver_name,
                target_ip=target_ip,
                success=False,
                error=f"Unexpected error: {exc}",
                command=cmd_str,
            )

    async def trace_all(self) -> list[TracerouteResult]:
        """Run traceroute to all configured resolvers."""
        tasks = [self.trace_resolver(name) for name in self.resolvers]
        return await asyncio.gather(*tasks)

    def print_results(self, results: list[TracerouteResult], json_output: bool = False) -> None:
        """Print traceroute results to stdout."""
        if json_output:
            print(json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False))
            return

        for result in results:
            print(f"\n=== Traceroute to {result.resolver_name} ({result.target_ip}) ===")
            print(f"Command: {result.command}")
            if not result.success:
                print(f"ERROR: {result.error}")
                continue

            if not result.hops:
                print("  No hops recorded")
                continue

            for hop in result.hops:
                if hop.ip:
                    rtt_str = f"  rtt={hop.rtt_ms:.2f}ms" if hop.rtt_ms else "  rtt=*"
                    if hop.rtt_ms_list:
                        rtt_str += f" [{', '.join(f'{x:.2f}' for x in hop.rtt_ms_list)}ms]"
                    print(f"  {hop.ttl:2d}  {hop.ip:15s} {rtt_str}")
                else:
                    print(f"  {hop.ttl:2d}  * * *")


__all__ = ["TracerouteAgent", "TracerouteResult", "Hop"]