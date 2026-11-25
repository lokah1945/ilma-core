#!/usr/bin/env python3
"""
Verify a single OoklaServer instance.
Usage: python3 verify_ookla_server.py <ip> <domain> [port]
"""
import socket
import sys

def verify_ookla_server(ip, host_header, port=8080, use_ipv6=False, timeout=5):
    """Verify server responds with 'It worked!'."""
    try:
        if use_ipv6:
            sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            sock.connect((ip, port, 0, 0))
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((ip, port))
        
        sock.settimeout(timeout)
        request = f"GET / HTTP/1.1\r\nHost: {host_header}\r\nUser-Agent: curl/7.88.1\r\nAccept: */*\r\nConnection: close\r\n\r\n"
        sock.sendall(request.encode())
        resp = sock.recv(4096).decode('utf-8', errors='ignore')
        sock.close()
        
        if 'It worked!' in resp:
            return True, "WORKED", resp[:500]
        elif 'HTTP/1.1 200' in resp or 'HTTP/1.0 200' in resp:
            return True, "HTTP_200_NO_WORKED", resp[:500]
        elif '307 Temporary Redirect' in resp:
            return True, "REDIRECT_307", resp[:500]
        elif '500 Internal Server Error' in resp:
            return False, "ERROR_500", resp[:500]
        else:
            return False, "OTHER", resp[:200]
    except socket.timeout:
        return False, "TIMEOUT", ""
    except ConnectionRefusedError:
        return False, "REFUSED", ""
    except Exception as e:
        return False, f"ERROR_{type(e).__name__}", str(e)

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 verify_ookla_server.py <ip> <domain> [port]")
        print("Example: python3 verify_ookla_server.py 103.155.190.76 surabaya.trisuladata.net.id")
        print("         python3 verify_ookla_server.py 2406:7540:1900::190:76 surabaya.trisuladata.net.id")
        sys.exit(1)
    
    ip = sys.argv[1]
    domain = sys.argv[2]
    port = int(sys.argv[3]) if len(sys.argv) > 3 else 8080
    
    is_ipv6 = ':' in ip
    host_header = f"{domain}:{port}"
    
    print(f"Verifying {ip} ({'IPv6' if is_ipv6 else 'IPv4'}) with Host: {host_header}...")
    
    ok, status, resp = verify_ookla_server(ip, host_header, port, is_ipv6)
    
    if ok and status == "WORKED":
        print(f"✅ SUCCESS: OoklaServer confirmed")
        print(f"Response: {resp[:200]}")
    elif ok:
        print(f"⚠️  HTTP {status}: {resp[:200]}")
    else:
        print(f"❌ FAILED: {status}")
        if resp:
            print(f"Details: {resp}")
    
    sys.exit(0 if ok and status == "WORKED" else 1)

if __name__ == '__main__':
    main()