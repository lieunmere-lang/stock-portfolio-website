#!/usr/bin/env python3
import base64
import os
import argparse
import http.client
import http.server
import socketserver
import urllib.parse
from pathlib import Path

DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 8001
BACKEND_HOST = '127.0.0.1'
BACKEND_PORT = 8000
ENV_FILE = Path(__file__).resolve().parent.parent / 'backend' / '.env'


def load_env(path):
    values = {}
    if not path.exists():
        return values
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, value = line.split('=', 1)
            values[key.strip()] = value.strip()
    return values


def get_expected_token(env):
    user = env.get('APP_USERNAME', 'portfolio')
    password = env.get('APP_PASSWORD', 'portfolio')
    raw = f"{user}:{password}"
    return base64.b64encode(raw.encode('utf-8')).decode('utf-8')


env = load_env(ENV_FILE)
EXPECTED_TOKEN = get_expected_token(env)
AUTH_HEADER = f"Basic {EXPECTED_TOKEN}"


class AuthHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_AUTHHEAD(self):
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="Protected Portfolio"')
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()

    def is_authenticated(self):
        auth_header = self.headers.get('Authorization')
        if not auth_header:
            return False
        return auth_header.strip() == AUTH_HEADER

    def proxy_to_backend(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        if parsed_path.query:
            path += '?' + parsed_path.query

        conn = http.client.HTTPConnection(BACKEND_HOST, BACKEND_PORT)
        headers = {}
        for key, value in self.headers.items():
            header_name = key.lower()
            if header_name in ('host', 'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'te', 'trailers', 'transfer-encoding', 'upgrade'):
                continue
            headers[key] = value

        headers['Host'] = f"{BACKEND_HOST}:{BACKEND_PORT}"
        headers['Authorization'] = AUTH_HEADER

        body = None
        if self.command in ('POST', 'PUT', 'PATCH'):
            length = int(self.headers.get('Content-Length', '0'))
            if length:
                body = self.rfile.read(length)

        conn.request(self.command, path, body=body, headers=headers)
        response = conn.getresponse()

        self.send_response(response.status, response.reason)
        for key, value in response.getheaders():
            if key.lower() in ('transfer-encoding', 'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'te', 'trailers', 'upgrade'):
                continue
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(response.read())
        conn.close()

    def do_GET(self):
        if not self.is_authenticated():
            self.do_AUTHHEAD()
            self.wfile.write(b'Unauthorized')
            return

        parsed_path = urllib.parse.urlparse(self.path)
        route = parsed_path.path
        if route.startswith('/api/'):
            self.proxy_to_backend()
            return
        if route in ('', '/', '/index.html'):
            self.serve_index()
            return
        super().do_GET()

    def do_POST(self):
        if not self.is_authenticated():
            self.do_AUTHHEAD()
            self.wfile.write(b'Unauthorized')
            return

        parsed_path = urllib.parse.urlparse(self.path)
        route = parsed_path.path
        if route.startswith('/api/'):
            self.proxy_to_backend()
            return
        super().do_POST()

    def do_HEAD(self):
        if not self.is_authenticated():
            self.do_AUTHHEAD()
            return
        super().do_HEAD()

    def serve_index(self):
        file_path = Path(self.translate_path('/index.html'))
        if not file_path.exists():
            self.send_error(404, 'File not found')
            return

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        content = content.replace('__BASIC_AUTH_HEADER__', AUTH_HEADER)

        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(content.encode('utf-8'))))
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))


def run(host, port):
    os.chdir(Path(__file__).resolve().parent)
    handler = AuthHTTPRequestHandler
    with socketserver.ThreadingTCPServer((host, port), handler) as httpd:
        print(f'Serving frontend at http://{host}:{port}')
        httpd.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run authenticated frontend server')
    parser.add_argument('--host', default=DEFAULT_HOST, help='Host to bind')
    parser.add_argument('--port', default=DEFAULT_PORT, type=int, help='Port to bind')
    args = parser.parse_args()
    run(args.host, args.port)
