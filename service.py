"""Small service whose dependencies can be deliberately broken in the lab."""
import http.server
import json
import os
from pathlib import Path


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            config = json.loads(Path('/etc/lab/config.json').read_text())
            if config.get('message') != 'ready':
                raise ValueError('invalid message configuration')
            Path('/var/lib/lab/probe').write_text('health-check\n')
            code, result = 200, {'status': 'healthy'}
        except (OSError, ValueError) as error:
            code, result = 503, {'status': 'unhealthy', 'error': str(error)}
        body = json.dumps(result).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


http.server.ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
