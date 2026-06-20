#!/usr/bin/env python3
"""
OAuth Callback Server — captures authorization code from redirect.
Runs on http://localhost:1455/auth/callback
"""

import sys
import os
import json
import time
import threading
import urllib.parse

try:
    from http.server import HTTPServer, BaseHTTPRequestHandler
except ImportError:
    from http.server import HTTPServer, BaseHTTPRequestHandler

CALLBACK_DATA = {'code': None, 'state': None, 'received_at': None, 'error': None}
CALLBACK_FILE = '/root/.hermes/profiles/ilma/scripts/.oauth_callback.json'
PORT = 1455

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # Silent
    
    def do_GET(self):
        global CALLBACK_DATA
        
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        
        code = params.get('code', [None])[0]
        state = params.get('state', [None])[0]
        error = params.get('error', [None])[0]
        
        CALLBACK_DATA = {
            'code': code,
            'state': state,
            'error': error,
            'received_at': time.time(),
            'path': self.path
        }
        
        # Save to file
        with open(CALLBACK_FILE, 'w') as f:
            json.dump(CALLBACK_DATA, f, indent=2)
        
        # Send response
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        
        if error:
            msg = "OAuth Error: " + str(error)
            html = f"<html><body style=\"font-family:sans-serif;padding:40px;text-align:center;\"><h2 style=\"color:red;\">OAuth Error</h2><p>Error: {error}</p></body></html>".encode()
        else:
            html = b"<html><body style=\"font-family:sans-serif;padding:40px;text-align:center;\"><h2 style=\"color:green;\">SUCCESS</h2><p>You can close this window.</p></body></html>"
        self.wfile.write(html)
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        parsed = urllib.parse.parse_qs(body)
        code = parsed.get('code', [None])[0]
        state = parsed.get('state', [None])[0]
        
        global CALLBACK_DATA
        CALLBACK_DATA = {
            'code': code,
            'state': state,
            'received_at': time.time(),
            'path': self.path,
            'method': 'POST'
        }
        
        with open(CALLBACK_FILE, 'w') as f:
            json.dump(CALLBACK_DATA, f, indent=2)
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(b"<html><body><h2>OK</h2></body></html>")


def start_server():
    server = HTTPServer(('127.0.0.1', PORT), Handler)
    server.allow_reuse_address = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[CallbackServer] Running on http://127.0.0.1:{PORT}")
    return server


def wait_for_callback(timeout=300):
    """Wait for callback data file to be written."""
    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(CALLBACK_FILE):
            try:
                with open(CALLBACK_FILE) as f:
                    data = json.load(f)
                if data.get('code'):
                    return data
            except:
                pass
        time.sleep(1)
    return None


def get_callback_data():
    """Get latest callback data."""
    if os.path.exists(CALLBACK_FILE):
        try:
            with open(CALLBACK_FILE) as f:
                return json.load(f)
        except:
            pass
    return CALLBACK_DATA


if __name__ == '__main__':
    server = start_server()
    print("Callback server running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.shutdown()