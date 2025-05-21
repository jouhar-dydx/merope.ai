from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import logging
import os

class SimpleServer(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/healthz':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy", "module": "model_engine"}).encode())
        else:
            self.send_response(404)

logger = logging.getLogger("ModelEngine")
logger.setLevel(logging.INFO)

log_dir = "/logs/merope"
os.makedirs(log_dir, exist_ok=True)

file_handler = logging.FileHandler(os.path.join(log_dir, "model_engine.log"))
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(file_handler.formatter)
logger.addHandler(console_handler)

if __name__ == "__main__":
    print("Starting Model Engine Service...")
    server = HTTPServer(('0.0.0.0', 8080), SimpleServer)
    server.serve_forever()