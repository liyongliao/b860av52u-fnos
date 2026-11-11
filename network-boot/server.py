"""Serve three public boot artifacts and receive bounded diagnostic reports."""
from pathlib import Path
import socket, struct, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer

import argparse
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent/'artifacts')
parser.add_argument('--logs', type=Path, default=Path('logs'))
parser.add_argument('--bind', default='0.0.0.0')
parser.add_argument('--port', type=int, default=69)
parser.add_argument('--report-port', type=int, default=8769)
a=parser.parse_args()
FILES={n:str(a.root/n) for n in ('Image','diag.uimg','board.dtb','boot.img','hybrid.dtb')}
LOG=a.logs
LOG.mkdir(parents=True,exist_ok=True)

class Reports(BaseHTTPRequestHandler):
    def do_POST(self):
        size = int(self.headers.get('Content-Length', '0'))
        if self.path not in ('/diag', '/kernel') or not 0 < size < 262144:
            self.send_error(400)
            return
        data = self.rfile.read(size)
        (LOG / (self.path[1:] + '.txt')).write_bytes(data)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')
        print('REPORT', self.path, len(data), flush=True)
    def log_message(self, *args):
        pass

threading.Thread(target=HTTPServer((a.bind, a.report_port), Reports).serve_forever, daemon=True).start()
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((a.bind, a.port))
print('READY TFTP69 REPORT8769', flush=True)
while True:
    sock.settimeout(None)
    request, peer = sock.recvfrom(4096)
    if request[:2] != b'\0\1':
        continue
    fields = request[2:].split(b'\0')
    name = fields[0].decode(errors='replace')
    if name not in FILES:
        sock.sendto(b'\0\5\0\1Not found\0', peer)
        continue
    data = Path(FILES[name]).read_bytes()
    options = dict(zip(fields[2:-1:2], fields[3:-1:2]))
    blocksize = min(1468, max(8, int(options.get(b'blksize', b'512'))))
    def exchange(packet, block):
        sock.settimeout(2)
        for attempt in range(8):
            sock.sendto(packet, peer)
            try:
                while True:
                    response, sender = sock.recvfrom(4096)
                    if sender == peer and response == struct.pack('>HH', 4, block):
                        return True
            except socket.timeout:
                continue
        return False
    print('START', name, len(data), peer, 'block', blocksize, flush=True)
    start = time.monotonic()
    oack = b''
    if b'blksize' in options:
        oack += b'blksize\0' + str(blocksize).encode() + b'\0'
    if b'tsize' in options:
        oack += b'tsize\0' + str(len(data)).encode() + b'\0'
    if oack and not exchange(b'\0\6' + oack, 0):
        print('OACK failed', flush=True)
        continue
    success = True
    for index, offset in enumerate(range(0, len(data) + 1, blocksize), 1):
        block = index & 65535
        if not exchange(struct.pack('>HH', 3, block) + data[offset:offset + blocksize], block):
            success = False
            break
    print('END', name, success, round(time.monotonic() - start, 2), flush=True)
