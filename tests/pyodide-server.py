"""
Pyodide 测试用 server - 设置正确的 MIME types
用法: python tests/pyodide-server.py [port]
"""
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path


class PyodideHTTPRequestHandler(SimpleHTTPRequestHandler):
    """Set correct MIME types for .wasm and other assets"""

    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        '.wasm': 'application/wasm',
        '.mjs': 'application/javascript',
        '.js': 'application/javascript',
        '.json': 'application/json',
        '.py': 'text/plain',
        '.zip': 'application/zip',
        '.csv': 'text/csv',
        '.data': 'application/octet-stream',
        '': 'application/octet-stream',
    }

    def end_headers(self):
        # Allow SharedArrayBuffer (Pyodide webworker mode)
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        # Disable caching during development
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    # serve from project root
    root = Path(__file__).parent.parent
    import os
    os.chdir(root)

    server = HTTPServer(('127.0.0.1', port), PyodideHTTPRequestHandler)
    print(f'Pyodide test server: http://127.0.0.1:{port}/')
    print(f'   serving from: {root}')
    print(f'   index: http://127.0.0.1:{port}/templates/index.html')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == '__main__':
    main()
