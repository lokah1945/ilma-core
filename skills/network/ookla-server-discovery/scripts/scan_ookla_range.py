#!/usr/bin/env python3
"""
Scan IP ranges for OoklaServer instances using Speedtest.net API.
Usage: python3 scan_ookla_range.py <cidr1> <cidr2> ...
"""
import socket
import json
import sys
import urllib.request
from ipaddress import IPv4Network, IPv6Network
from concurrent.futures import ThreadPoolExecutor, as_completed

SPEEDTEST_API = "https://www.speedtest.net/api/js/servers?engine=js&limit=2000"
TIMEOUT = 5
MAX_WORKERS = 50

def fetch_servers():
    """Fetch server list from Speedtest.net API."""
    with urllib.request.urlopen(SPEEDTEST_API, timeout=30) as resp:
        return json.load(resp)

def clean_hostname(host):
    """Remove .prod.hosts.ooklaserver.net suffix."""
    return host.replace('.prod.hosts.ooklaserver.net', '').split(':')[0]

def resolve_host(host):
    """Resolve hostname to IPv4 and IPv6 addresses."""
    ips = {'ipv4': [], 'ipv6': []}
    try:
        for family, _, _, _, sockaddr in socket.getaddrinfo(host, 8080, 0, socket.SOCK_STREAM):
            if family == socket.AF_INET:
                ips['ipv4'].append(sockaddr[0])
            elif family == socket.AF_INET6:
                ips['ipv6'].append(sockaddr[0])
    except Exception:
        pass
    # Deduplicate
    ips['ipv4'] = list(set(ips['ipv4']))
    ips['ipv6'] = list(set(ips['ipv6']))
    return ips

def ip_in_ranges(ip, ranges):
    """Check if IP is in any of the target CIDR ranges."""
    import ipaddress
    try:
        ip_obj = ipaddress.ip_address(ip)
        for cidr in ranges:
            network = ipaddress.ip_network(cidr, strict=False)
            if ip_obj in network:
                return True
    except Exception:
        pass
    return False

def verify_ookla_server(ip, host_header, port=8080, use_ipv6=False):
    """Verify server responds with 'It worked!'."""
    try:
        if use_ipv6:
            sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            sock.connect((ip, port, 0, 0))
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((ip, port))
        
        sock.settimeout(TIMEOUT)
        request = f"GET / HTTP/1.1\r\nHost: {host_header}\r\nUser-Agent: curl/7.88.1\r\nAccept: */*\r\nConnection: close\r\n\r\n"
        sock.sendall(request.encode())
        resp = sock.recv(4096).decode('utf-8', errors='ignore')
        sock.close()
        
        if 'It worked!' in resp:
            return True, resp[:500]
        elif 'HTTP/1.1 200' in resp or 'HTTP/1.0 200' in resp:
            return 'http', resp[:500]
        return False, resp[:200]
    except Exception as e:
        return False, str(e)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scan_ookla_range.py <cidr1> [cidr2] ...")
        print("Example: python3 scan_ookla_range.py 103.155.190.0/24 103.155.191.0/24")
        sys.exit(1)
    
    ranges = sys.argv[1:]
    
    print(f"Fetching server list from Speedtest.net...")
    servers = fetch_servers()
    print(f"Got {len(servers)} servers")
    
    # Resolve all hosts and filter by range
    candidates = []
    print("Resolving hostnames...")
    for s in servers:
        host = clean_hostname(s['host'])
        ips = resolve_host(host)
        for ip in ips['ipv4'] + ips['ipv6']:
            if ip_in_ranges(ip, ranges):
                candidates.append({
                    'server': s,
                    'ip': ip,
                    'is_ipv6': ':' in ip,
                    'host': host
                })
    
    print(f"Found {len(candidates)} candidate IPs in target ranges")
    
    # Verify each candidate
    worked = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for c in candidates:
            host_header = f"{c['host']}:8080"
            futures[executor.submit(verify_ookla_server, c['ip'], host_header, 8080, c['is_ipv6'])] = c
        
        for future in as_completed(futures):
            c = futures[future]
            ok, resp = future.result()
            if ok is True:
                worked.append({
                    'ip': c['ip'],
                    'ipv6': c['ip'] if c['is_ipv6'] else None,
                    'host': c['host'],
                    'port': 8080,
                    'server_id': c['server']['id'],
                    'sponsor': c['server']['sponsor'],
                    'status': 'WORKED',
                    'accessible_via': 'IPv6' if c['is_ipv6'] else 'IPv4',
                    'response': resp
                })
                print(f"✅ WORKED: {c['ip']} ({c['host']})")
    
    # Output JSON
    result = {
        'scan_time': __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'ranges_scanned': ranges,
        'total_servers_checked': len(servers),
        'candidates_in_range': len(candidates),
        'worked_servers': worked
    }
    
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()