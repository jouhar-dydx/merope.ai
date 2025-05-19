from http.server import BaseHTTPRequestHandler, HTTPServer
import json

class SimpleServer(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/healthz':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy", "module": "data_processor"}).encode())
        else:
            self.send_response(404)

if __name__ == "__main__":
    print("Starting Data Processor Service...")
    server = HTTPServer(('0.0.0.0', 8080), SimpleServer)
    server.serve_forever()