#!/usr/bin/env python3
"""
ILMA Network Toolkit
===================
Comprehensive networking capability with DNS resolution, firewall management,
and network diagnostics.

Classes: DNSResolver, FirewallManager, NetworkDiagnostics

Usage:
    python3 ilma_network_toolkit.py --resolve "example.com"
    python3 ilma_network_toolkit.py --check-port 80 --host example.com
    python3 ilma_network_toolkit.py --list-rules
    python3 ilma_network_toolkit.py --diag --target 192.168.1.1

Author: ILMA v5.0
Version: 1.0.0
"""

from __future__ import annotations

import argparse
import ipaddress
import logging
import os
import re
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("NetworkToolkit")


# =============================================================================
# ENUMS AND DATA STRUCTURES
# =============================================================================

class Protocol(Enum):
    """Network protocols."""
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"


class FirewallRuleAction(Enum):
    """Firewall rule actions."""
    ALLOW = "allow"
    DENY = "deny"
    DROP = "drop"
    REJECT = "reject"


@dataclass
class DNSRecord:
    """DNS record representation."""
    name: str
    record_type: str
    value: str
    ttl: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PortCheckResult:
    """Port check result."""
    host: str
    port: int
    protocol: Protocol
    is_open: bool
    response_time_ms: Optional[float] = None
    service_name: Optional[str] = None


@dataclass
class FirewallRule:
    """Firewall rule representation."""
    id: str
    action: FirewallRuleAction
    protocol: Protocol
    source_ip: Optional[str] = None
    dest_ip: Optional[str] = None
    source_port: Optional[int] = None
    dest_port: Optional[int] = None
    interface: Optional[str] = None
    comment: str = ""
    enabled: bool = True


# =============================================================================
# DNS RESOLVER CLASS
# =============================================================================

class DNSResolver:
    """
    DNS resolution with support for multiple record types,
    caching, and fallback resolution strategies.
    """
    
    COMMON_PORTS = {
        21: "ftp",
        22: "ssh",
        23: "telnet",
        25: "smtp",
        53: "dns",
        80: "http",
        110: "pop3",
        143: "imap",
        443: "https",
        993: "imaps",
        995: "pop3s",
        3306: "mysql",
        5432: "postgresql",
        6379: "redis",
        27017: "mongodb"
    }
    
    def __init__(self, cache_enabled: bool = True, cache_ttl: int = 300):
        self.cache_enabled = cache_enabled
        self.cache_ttl = cache_ttl
        self.cache: Dict[str, Tuple[DNSRecord, float]] = {}
        logger.info("DNSResolver initialized")
    
    def resolve(self, hostname: str, record_type: str = "A") -> List[DNSRecord]:
        """Resolve hostname to DNS records."""
        cache_key = f"{hostname}:{record_type}"
        
        # Check cache
        if self.cache_enabled and cache_key in self.cache:
            record, cached_time = self.cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                logger.debug(f"Cache hit for {hostname}")
                return [record]
        
        try:
            if record_type == "A":
                ip = socket.gethostbyname(hostname)
                record = DNSRecord(
                    name=hostname,
                    record_type="A",
                    value=ip,
                    ttl=300
                )
                self._cache_record(cache_key, record)
                return [record]
            
            elif record_type == "AAAA":
                # IPv6 resolution
                results = []
                try:
                    addr_info = socket.getaddrinfo(hostname, None, socket.AF_INET6)
                    for info in addr_info:
                        ip = info[4][0]
                        results.append(DNSRecord(
                            name=hostname,
                            record_type="AAAA",
                            value=ip,
                            ttl=300
                        ))
                except socket.gaierror:
                    pass
                return results if results else []
            
            elif record_type == "MX":
                # MX record lookup
                try:
                    import dns.resolver
                    answers = dns.resolver.resolve(hostname, 'MX')
                    records = []
                    for rdata in answers:
                        records.append(DNSRecord(
                            name=hostname,
                            record_type="MX",
                            value=f"{rdata.preference} {rdata.exchange}",
                            ttl=300
                        ))
                    return records
                except ImportError:
                    logger.warning("dnspython not installed, MX lookup unavailable")
                    return []
                except Exception as e:
                    logger.error(f"MX lookup failed: {e}")
                    return []
            
            elif record_type == "TXT":
                try:
                    import dns.resolver
                    answers = dns.resolver.resolve(hostname, 'TXT')
                    records = []
                    for rdata in answers:
                        records.append(DNSRecord(
                            name=hostname,
                            record_type="TXT",
                            value="".join(rdata.strings),
                            ttl=300
                        ))
                    return records
                except ImportError:
                    return []
                except Exception as e:
                    logger.error(f"TXT lookup failed: {e}")
                    return []
            
            else:
                logger.warning(f"Unsupported record type: {record_type}")
                return []
                
        except socket.gaierror as e:
            logger.error(f"DNS resolution failed for {hostname}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected DNS error: {e}")
            return []
    
    def reverse_lookup(self, ip: str) -> Optional[str]:
        """Perform reverse DNS lookup."""
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            return hostname
        except (socket.herror, socket.gaierror) as e:
            logger.debug(f"Reverse lookup failed for {ip}: {e}")
            return None
    
    def _cache_record(self, key: str, record: DNSRecord) -> None:
        """Cache a DNS record."""
        self.cache[key] = (record, time.time())
    
    def clear_cache(self) -> None:
        """Clear the DNS cache."""
        self.cache.clear()
        logger.info("DNS cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "entries": len(self.cache),
            "enabled": self.cache_enabled,
            "ttl": self.cache_ttl
        }


# =============================================================================
# FIREWALL MANAGER CLASS
# =============================================================================

class FirewallManager:
    """
    Firewall rule management with support for iptables/nftables.
    Provides rule creation, listing, and maintenance capabilities.
    """
    
    def __init__(self, backend: str = "iptables"):
        self.backend = backend
        self.rules_file = Path("/etc/ilma_firewall_rules.conf")
        self._ensure_permissions()
        logger.info(f"FirewallManager initialized with {backend}")
    
    def _ensure_permissions(self) -> bool:
        """Check if we have necessary permissions."""
        if os.geteuid() != 0:
            logger.warning("Not running as root, firewall operations may fail")
            return False
        return True
    
    def add_rule(self, rule: FirewallRule) -> bool:
        """Add a firewall rule."""
        try:
            cmd = self._build_rule_command(rule, "append")
            
            if self.backend == "iptables":
                result = subprocess.run(
                    ["iptables"] + cmd,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    self._save_rule_to_file(rule)
                    logger.info(f"Added rule: {rule.id}")
                    return True
                else:
                    logger.error(f"Failed to add rule: {result.stderr}")
                    return False
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to add firewall rule: {e}")
            return False
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove a firewall rule by ID."""
        try:
            # Build and execute deletion command
            if self.backend == "iptables":
                # Parse saved rules to find the rule
                saved_rules = self._load_saved_rules()
                for rule in saved_rules:
                    if rule.id == rule_id:
                        cmd = self._build_deletion_command(rule)
                        result = subprocess.run(
                            ["iptables"] + cmd,
                            capture_output=True,
                            text=True
                        )
                        if result.returncode == 0:
                            logger.info(f"Removed rule: {rule_id}")
                            return True
                
            return False
            
        except Exception as e:
            logger.error(f"Failed to remove firewall rule: {e}")
            return False
    
    def list_rules(self, format: str = "table") -> str:
        """List current firewall rules."""
        try:
            if self.backend == "iptables":
                result = subprocess.run(
                    ["iptables", "-L", "-n", "--line-numbers"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    if format == "raw":
                        return result.stdout
                    
                    # Parse and format
                    lines = result.stdout.split("\n")
                    header = lines[0] if lines else ""
                    return result.stdout
                else:
                    return f"Failed to list rules: {result.stderr}"
            
            return "Unsupported backend"
            
        except Exception as e:
            logger.error(f"Failed to list firewall rules: {e}")
            return str(e)
    
    def flush_rules(self, chain: str = "INPUT") -> bool:
        """Flush rules from a chain."""
        try:
            if self.backend == "iptables":
                result = subprocess.run(
                    ["iptables", "-F", chain],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    logger.info(f"Flushed {chain} chain")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to flush rules: {e}")
            return False
    
    def _build_rule_command(self, rule: FirewallRule, operation: str) -> List[str]:
        """Build iptables command for a rule."""
        cmd = []
        
        if operation == "append":
            cmd = ["-A"]
        elif operation == "delete":
            cmd = ["-D"]
        
        # Chain
        cmd.append("INPUT")
        
        # Action
        action_map = {
            FirewallRuleAction.ALLOW: "-j ACCEPT",
            FirewallRuleAction.DENY: "-j DROP",
            FirewallRuleAction.REJECT: "-j REJECT"
        }
        cmd.extend(action_map[rule.action].split())
        
        # Protocol
        if rule.protocol != Protocol.TCP:
            cmd.extend(["-p", rule.protocol.value])
        
        # Destination port
        if rule.dest_port:
            cmd.extend(["--dport", str(rule.dest_port)])
        
        # Source IP
        if rule.source_ip:
            cmd.extend(["-s", rule.source_ip])
        
        # Comment
        if rule.comment:
            cmd.extend(["-m", "comment", "--comment", rule.comment])
        
        return cmd
    
    def _build_deletion_command(self, rule: FirewallRule) -> List[str]:
        """Build iptables deletion command."""
        return self._build_rule_command(rule, "delete")
    
    def _save_rule_to_file(self, rule: FirewallRule) -> None:
        """Save rule configuration to file."""
        with open(self.rules_file, "a") as f:
            f.write(f"{rule.id}|{rule.action.value}|{rule.protocol.value}|")
            f.write(f"{rule.source_ip or ''}|{rule.dest_ip or ''}|")
            f.write(f"{rule.source_port or ''}|{rule.dest_port or ''}|")
            f.write(f"{rule.comment}\n")
    
    def _load_saved_rules(self) -> List[FirewallRule]:
        """Load saved rules from file."""
        rules = []
        
        if not self.rules_file.exists():
            return rules
        
        with open(self.rules_file) as f:
            for line in f:
                parts = line.strip().split("|")
                if len(parts) >= 8:
                    rule = FirewallRule(
                        id=parts[0],
                        action=FirewallRuleAction(parts[1]),
                        protocol=Protocol(parts[2]),
                        source_ip=parts[3] or None,
                        dest_ip=parts[4] or None,
                        source_port=int(parts[5]) if parts[5] else None,
                        dest_port=int(parts[6]) if parts[6] else None,
                        comment=parts[7]
                    )
                    rules.append(rule)
        
        return rules


# =============================================================================
# NETWORK DIAGNOSTICS CLASS
# =============================================================================

class NetworkDiagnostics:
    """
    Network diagnostics including ping, port scanning, traceroute,
    and connectivity analysis.
    """
    
    def __init__(self):
        self.results_history: List[Dict[str, Any]] = []
        logger.info("NetworkDiagnostics initialized")
    
    def ping(
        self,
        host: str,
        count: int = 4,
        timeout: int = 5
    ) -> Dict[str, Any]:
        """Perform ping to a host."""
        try:
            result = subprocess.run(
                ["ping", "-c", str(count), "-W", str(timeout), host],
                capture_output=True,
                text=True
            )
            
            output = result.stdout
            stats = self._parse_ping_output(output)
            
            return {
                "host": host,
                "reachable": result.returncode == 0,
                "packets_transmitted": stats.get("transmitted", 0),
                "packets_received": stats.get("received", 0),
                "packet_loss_percent": stats.get("loss", 100),
                "min_rtt_ms": stats.get("min", None),
                "avg_rtt_ms": stats.get("avg", None),
                "max_rtt_ms": stats.get("max", None),
                "raw_output": output[:500]
            }
            
        except Exception as e:
            logger.error(f"Ping failed: {e}")
            return {
                "host": host,
                "reachable": False,
                "error": str(e)
            }
    
    def check_port(
        self,
        host: str,
        port: int,
        protocol: Protocol = Protocol.TCP,
        timeout: int = 3
    ) -> PortCheckResult:
        """Check if a port is open on a host."""
        start_time = time.time()
        
        try:
            sock_type = socket.SOCK_STREAM if protocol == Protocol.TCP else socket.SOCK_DGRAM
            sock = socket.socket(socket.AF_INET, sock_type)
            sock.settimeout(timeout)
            
            result = sock.connect_ex((host, port))
            response_time = (time.time() - start_time) * 1000
            
            is_open = result == 0
            sock.close()
            
            service_name = DNSResolver.COMMON_PORTS.get(port, "unknown")
            
            return PortCheckResult(
                host=host,
                port=port,
                protocol=protocol,
                is_open=is_open,
                response_time_ms=response_time if is_open else None,
                service_name=service_name
            )
            
        except socket.timeout:
            return PortCheckResult(
                host=host,
                port=port,
                protocol=protocol,
                is_open=False
            )
        except Exception as e:
            logger.error(f"Port check failed: {e}")
            return PortCheckResult(
                host=host,
                port=port,
                protocol=protocol,
                is_open=False
            )
    
    def scan_ports(
        self,
        host: str,
        ports: List[int],
        protocol: Protocol = Protocol.TCP,
        timeout: int = 2
    ) -> List[PortCheckResult]:
        """Scan multiple ports on a host."""
        results = []
        
        for port in ports:
            result = self.check_port(host, port, protocol, timeout)
            results.append(result)
        
        open_ports = [r for r in results if r.is_open]
        logger.info(f"Port scan complete: {len(open_ports)}/{len(ports)} open on {host}")
        
        return results
    
    def traceroute(self, host: str, max_hops: int = 30) -> List[Dict[str, Any]]:
        """Perform traceroute to a host."""
        hops = []
        
        try:
            result = subprocess.run(
                ["traceroute", "-m", str(max_hops), "-n", host],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            for line in result.stdout.split("\n"):
                if line.strip() and not line.startswith("traceroute"):
                    match = re.match(r"\s*(\d+)\s+([^\s]+)\s+([^\s]+)\s+([^\s]+)", line)
                    if match:
                        hops.append({
                            "hop": int(match.group(1)),
                            "ip": match.group(2),
                            "rtt1": match.group(3),
                            "rtt2": match.group(4) if len(match.groups()) > 3 else None
                        })
            
        except subprocess.TimeoutExpired:
            logger.warning(f"Traceroute timed out for {host}")
        except Exception as e:
            logger.error(f"Traceroute failed: {e}")
        
        return hops
    
    def check_connectivity(self, targets: Optional[List[str]] = None) -> Dict[str, Any]:
        """Check network connectivity to multiple targets."""
        if targets is None:
            targets = ["8.8.8.8", "1.1.1.1", "208.67.222.222"]
        
        results = {}
        
        for target in targets:
            ping_result = self.ping(target, count=2, timeout=3)
            results[target] = ping_result
        
        # Summary
        reachable = sum(1 for r in results.values() if r.get("reachable", False))
        
        return {
            "total_targets": len(targets),
            "reachable": reachable,
            "unreachable": len(targets) - reachable,
            "connectivity_score": (reachable / len(targets)) * 100 if targets else 0,
            "results": results
        }
    
    def _parse_ping_output(self, output: str) -> Dict[str, Any]:
        """Parse ping command output."""
        stats = {}
        
        # Parse packet statistics
        match = re.search(r"(\d+) packets transmitted, (\d+) received", output)
        if match:
            stats["transmitted"] = int(match.group(1))
            stats["received"] = int(match.group(2))
        
        # Parse packet loss
        match = re.search(r"(\d+)% packet loss", output)
        if match:
            stats["loss"] = int(match.group(1))
        
        # Parse RTT statistics
        match = re.search(r"rtt min/avg/max/mdev = ([^/]+)/([^/]+)/([^/]+)/([^\s]+)", output)
        if match:
            stats["min"] = float(match.group(1))
            stats["avg"] = float(match.group(2))
            stats["max"] = float(match.group(3))
        
        return stats
    
    def get_network_info(self) -> Dict[str, Any]:
        """Get current network interface information."""
        info = {
            "hostname": socket.gethostname(),
            "interfaces": {}
        }
        
        try:
            # Get all network interfaces
            import netifaces
            for iface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(iface)
                info["interfaces"][iface] = {
                    "addresses": addrs,
                    "ipv4": [],
                    "ipv6": []
                }
                
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        info["interfaces"][iface]["ipv4"].append(addr.get("addr"))
                
                if netifaces.AF_INET6 in addrs:
                    for addr in addrs[netifaces.AF_INET6]:
                        info["interfaces"][iface]["ipv6"].append(addr.get("addr"))
        
        except ImportError:
            logger.warning("netifaces not available, using fallback method")
            # Fallback to hostname lookup
            try:
                info["fqdn"] = socket.getfqdn()
            except Exception:
                pass
        
        return info


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="ILMA Network Toolkit - DNS, Firewall, and Network Diagnostics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # DNS Resolution
  %(prog)s --resolve "example.com"
  %(prog)s --resolve "example.com" --type AAAA
  %(prog)s --reverse-lookup 8.8.8.8
  
  # Port Check
  %(prog)s --check-port 443 --host example.com
  %(prog)s --scan-ports 80,443,8080 --host example.com
  
  # Firewall Management
  %(prog)s --list-rules
  %(prog)s --add-rule --action allow --port 8080 --protocol tcp
  %(prog)s --flush-rules
  
  # Network Diagnostics
  %(prog)s --ping 8.8.8.8
  %(prog)s --traceroute example.com
  %(prog)s --diag --target example.com
        """
    )
    
    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    # DNS Options
    parser.add_argument("--resolve", metavar="HOSTNAME", help="Resolve hostname to IP")
    parser.add_argument("--type", default="A", choices=["A", "AAAA", "MX", "TXT", "CNAME"], help="DNS record type")
    parser.add_argument("--reverse-lookup", metavar="IP", help="Reverse DNS lookup")
    
    # Port Options
    parser.add_argument("--check-port", type=int, metavar="PORT", help="Check if port is open")
    parser.add_argument("--scan-ports", metavar="PORTS", help="Scan multiple ports (comma-separated)")
    parser.add_argument("--host", default="localhost", help="Target host for port checks")
    parser.add_argument("--protocol", default="tcp", choices=["tcp", "udp"], help="Protocol to use")
    
    # Firewall Options
    parser.add_argument("--list-rules", action="store_true", help="List current firewall rules")
    parser.add_argument("--add-rule", action="store_true", help="Add a firewall rule")
    parser.add_argument("--remove-rule", metavar="RULE_ID", help="Remove a firewall rule")
    parser.add_argument("--flush-rules", action="store_true", help="Flush firewall rules")
    parser.add_argument("--action", choices=["allow", "deny", "drop", "reject"], help="Rule action")
    parser.add_argument("--port", type=int, help="Port for firewall rule")
    parser.add_argument("--src-ip", help="Source IP for firewall rule")
    parser.add_argument("--comment", default="", help="Comment for firewall rule")
    
    # Diagnostics Options
    parser.add_argument("--ping", metavar="HOST", help="Ping a host")
    parser.add_argument("--traceroute", metavar="HOST", help="Traceroute to a host")
    parser.add_argument("--diag", action="store_true", help="Run full diagnostics")
    parser.add_argument("--target", help="Target for diagnostics")
    parser.add_argument("--connectivity", action="store_true", help="Check internet connectivity")
    parser.add_argument("--network-info", action="store_true", help="Show network interface info")
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # DNS Resolution
        if args.resolve:
            resolver = DNSResolver()
            records = resolver.resolve(args.resolve, args.type)
            
            if records:
                print(f"\nDNS Resolution for {args.resolve} ({args.type}):")
                for record in records:
                    print(f"  {record.record_type}: {record.value}")
            else:
                print(f"No records found for {args.resolve}")
        
        # Reverse Lookup
        elif args.reverse_lookup:
            resolver = DNSResolver()
            hostname = resolver.reverse_lookup(args.reverse_lookup)
            
            if hostname:
                print(f"\nReverse lookup for {args.reverse_lookup}: {hostname}")
            else:
                print(f"No reverse DNS record for {args.reverse_lookup}")
        
        # Port Check
        elif args.check_port:
            diag = NetworkDiagnostics()
            protocol = Protocol.TCP if args.protocol == "tcp" else Protocol.UDP
            
            result = diag.check_port(args.host, args.check_port, protocol)
            
            print(f"\nPort Check: {args.host}:{args.check_port}/{protocol.value}")
            print(f"  Status: {'OPEN' if result.is_open else 'CLOSED'}")
            if result.response_time_ms:
                print(f"  Response Time: {result.response_time_ms:.2f}ms")
            print(f"  Service: {result.service_name}")
        
        # Port Scan
        elif args.scan_ports:
            diag = NetworkDiagnostics()
            ports = [int(p) for p in args.scan_ports.split(",")]
            protocol = Protocol.TCP if args.protocol == "tcp" else Protocol.UDP
            
            print(f"\nScanning {len(ports)} ports on {args.host}...")
            results = diag.scan_ports(args.host, ports, protocol)
            
            open_ports = [r for r in results if r.is_open]
            print(f"\nOpen ports: {len(open_ports)}/{len(ports)}")
            for r in results:
                status = "OPEN" if r.is_open else "CLOSED"
                print(f"  {r.port}/{r.protocol.value}: {status}")
        
        # Firewall - List Rules
        elif args.list_rules:
            fw = FirewallManager()
            rules = fw.list_rules()
            print("\nCurrent Firewall Rules:")
            print(rules)
        
        # Firewall - Add Rule
        elif args.add_rule:
            if not args.port:
                parser.error("--port is required when adding a rule")
            
            fw = FirewallManager()
            rule = FirewallRule(
                id=f"rule_{int(time.time())}",
                action=FirewallRuleAction(args.action or "allow"),
                protocol=Protocol(args.protocol),
                dest_port=args.port,
                source_ip=args.src_ip,
                comment=args.comment
            )
            
            if fw.add_rule(rule):
                print(f"Rule added successfully: {rule.id}")
            else:
                print("Failed to add rule (may require root privileges)")
        
        # Firewall - Remove Rule
        elif args.remove_rule:
            fw = FirewallManager()
            if fw.remove_rule(args.remove_rule):
                print(f"Rule removed: {args.remove_rule}")
            else:
                print("Failed to remove rule")
        
        # Firewall - Flush Rules
        elif args.flush_rules:
            fw = FirewallManager()
            if fw.flush_rules():
                print("Rules flushed successfully")
            else:
                print("Failed to flush rules")
        
        # Ping
        elif args.ping:
            diag = NetworkDiagnostics()
            result = diag.ping(args.ping)
            
            print(f"\nPing to {args.ping}:")
            print(f"  Reachable: {'Yes' if result['reachable'] else 'No'}")
            if result.get('packets_transmitted'):
                print(f"  Packets: {result['packets_received']}/{result['packets_transmitted']} received")
                print(f"  Loss: {result.get('packet_loss_percent', 'N/A')}%")
            if result.get('avg_rtt_ms'):
                print(f"  RTT: min={result['min_rtt_ms']:.2f}ms avg={result['avg_rtt_ms']:.2f}ms max={result['max_rtt_ms']:.2f}ms")
        
        # Traceroute
        elif args.traceroute:
            diag = NetworkDiagnostics()
            hops = diag.traceroute(args.traceroute)
            
            print(f"\nTraceroute to {args.traceroute}:")
            for hop in hops:
                print(f"  {hop['hop']:2d}. {hop['ip']}")
        
        # Full Diagnostics
        elif args.diag:
            diag = NetworkDiagnostics()
            target = args.target or "8.8.8.8"
            
            print(f"\nRunning diagnostics for {target}...")
            
            ping_result = diag.ping(target)
            print(f"\nPing Result: {'Reachable' if ping_result['reachable'] else 'Unreachable'}")
            
            # Quick port check
            common_ports = [80, 443, 22, 21, 25, 53]
            print(f"\nScanning common ports...")
            results = diag.scan_ports(target, common_ports, Protocol.TCP, timeout=2)
            
            print("Open ports:")
            for r in results:
                if r.is_open:
                    print(f"  {r.port} ({r.service_name})")
        
        # Connectivity Check
        elif args.connectivity:
            diag = NetworkDiagnostics()
            result = diag.check_connectivity()
            
            print("\nInternet Connectivity Check:")
            print(f"  Targets: {result['total_targets']}")
            print(f"  Reachable: {result['reachable']}")
            print(f"  Unreachable: {result['unreachable']}")
            print(f"  Score: {result['connectivity_score']:.0f}%")
        
        # Network Info
        elif args.network_info:
            diag = NetworkDiagnostics()
            info = diag.get_network_info()
            
            print(f"\nNetwork Information:")
            print(f"  Hostname: {info['hostname']}")
            print("  Interfaces:")
            for iface, data in info.get("interfaces", {}).items():
                print(f"    {iface}:")
                for ip in data.get("ipv4", []):
                    print(f"      IPv4: {ip}")
                for ip in data.get("ipv6", []):
                    print(f"      IPv6: {ip}")
        
        else:
            parser.print_help()
    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()