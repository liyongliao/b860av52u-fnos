"""Minimal ADB v1 transport for the user's legacy Android box.

Does not connect to any address other than the explicitly identified box.
Remote services run only when this module is invoked or call() is used.
"""
import argparse
import socket
import struct
import sys



def call(service, address, timeout=15):
    with socket.create_connection(address, timeout=5) as sock:
        sock.settimeout(timeout)

        def send(command, arg0, arg1, payload=b''):
            number = int.from_bytes(command, 'little')
            sock.sendall(struct.pack('<6I', number, arg0, arg1, len(payload),
                                     sum(payload) & 0xffffffff,
                                     number ^ 0xffffffff) + payload)

        def exact(size):
            result = bytearray()
            while len(result) < size:
                part = sock.recv(size - len(result))
                if not part:
                    raise EOFError('ADB connection closed')
                result.extend(part)
            return bytes(result)

        def receive():
            header = exact(24)
            number, arg0, arg1, size, checksum, magic = struct.unpack('<6I', header)
            if size > 1048576 or magic != number ^ 0xffffffff:
                raise ValueError('Invalid ADB packet')
            payload = exact(size)
            if sum(payload) & 0xffffffff != checksum:
                raise ValueError('ADB checksum mismatch')
            return header[:4], arg0, arg1, payload

        send(b'CNXN', 0x01000000, 4096, b'host::\0')
        command, _, _, identity = receive()
        if command != b'CNXN' or b'ro.product.model=B860AV5.2-U;' not in identity:
            raise RuntimeError('Unexpected identity or authorization required')
        send(b'OPEN', 1, 0, service.encode() + b'\0')
        result = bytearray()
        while True:
            command, remote, local, payload = receive()
            if local != 1:
                raise ValueError('Unexpected stream identifier')
            if command == b'WRTE':
                result.extend(payload)
                send(b'OKAY', 1, remote)
            elif command == b'CLSE':
                send(b'CLSE', 1, remote)
                return bytes(result)
            elif command != b'OKAY':
                raise RuntimeError(f'Unexpected packet {command!r}')


