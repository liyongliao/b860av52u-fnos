"""Strict RAW/FILL Android sparse codec, with independent expansion checking."""
from pathlib import Path
import hashlib, json, struct, sys

HEADER = struct.Struct('<IHHHHIIII')
CHUNK = struct.Struct('<HHII')
MAGIC, RAW, FILL = 0xed26ff3a, 0xcac1, 0xcac2
BLOCK, MAX_BLOCKS = 4096, 2048  # Keep individual expanded chunks <=8MiB.

def chunks(stream, size):
    start = stream.tell()
    header = stream.read(HEADER.size)
    if len(header) != HEADER.size:
        raise ValueError('Truncated sparse header')
    magic, major, minor, fh, ch, block, blocks, count, crc = HEADER.unpack(header)
    if (magic, major, minor, fh, ch, block, crc) != (MAGIC, 1, 0, 28, 12, BLOCK, 0):
        raise ValueError('Unsupported sparse header')
    if count * 12 + 28 > 2*1024*1024:
        raise ValueError('Exceeds stock U-Boot sparse header backup buffer')
    total = 0
    yield header, None, 0
    for _ in range(count):
        raw = stream.read(12)
        if len(raw) != 12: raise ValueError('Truncated chunk')
        kind, reserved, number, stored = CHUNK.unpack(raw)
        if reserved or not 0 < number <= MAX_BLOCKS:
            raise ValueError('Invalid or oversized sparse chunk')
        logical = number * BLOCK
        expected = logical if kind == RAW else 4 if kind == FILL else -1
        if expected < 0 or stored != 12 + expected:
            raise ValueError('Unsupported or malformed chunk; DONT_CARE is forbidden')
        payload = stream.read(expected)
        if len(payload) != expected: raise ValueError('Truncated payload')
        if kind == FILL and payload != bytes(4):
            raise ValueError('Only zero fill is permitted')
        yield raw, payload, logical
        total += number
    if total != blocks or stream.tell() - start != size:
        raise ValueError('Sparse block count or stored size mismatch')

def validate(stream, size, reference=None):
    logical_hash, stored_hash = hashlib.sha256(), hashlib.sha1()
    logical_size, data_reads, count = 0, 0, 0
    for head, payload, logical in chunks(stream, size):
        stored_hash.update(head)
        if payload is None: continue
        stored_hash.update(payload)
        expanded = payload if len(payload) == logical else bytes(logical)
        if reference is not None and reference.read(logical) != expanded:
            raise ValueError(f'Expanded bytes differ at offset {logical_size}')
        logical_hash.update(expanded)
        logical_size += logical
        data_reads += len(payload)
        count += 1
    if reference is not None and reference.read(1):
        raise ValueError('Reference image longer than sparse expansion')
    return dict(logical_bytes=logical_size, logical_sha256=logical_hash.hexdigest(),
                sparse_sha1=stored_hash.hexdigest(), stored_bytes=size,
                device_verification_read_bytes=data_reads, chunk_count=count)

def encode(source, destination):
    if destination.exists(): raise ValueError('Refusing overwrite')
    assert source.stat().st_size % BLOCK == 0
    zero = bytes(BLOCK)
    runs, last, number = [], None, 0
    with source.open('rb') as stream:
        while data := stream.read(4*1024*1024):
            for off in range(0, len(data), BLOCK):
                kind = FILL if data[off:off+BLOCK] == zero else RAW
                if kind != last or number == MAX_BLOCKS:
                    if number: runs.append((last, number))
                    last, number = kind, 0
                number += 1
        if number: runs.append((last, number))
    assert len(runs)*12+28 < 2*1024*1024
    with source.open('rb') as inp, destination.open('xb') as out:
        out.write(HEADER.pack(MAGIC, 1, 0, 28, 12, BLOCK,
                              source.stat().st_size//BLOCK, len(runs), 0))
        for kind, number in runs:
            data = inp.read(number*BLOCK)
            payload = bytes(4) if kind == FILL else data
            if kind == FILL and any(data): raise ValueError('Input changed during encoding')
            out.write(CHUNK.pack(kind, 0, number, 12+len(payload)))
            out.write(payload)
    with destination.open('rb') as inp, source.open('rb') as reference:
        report = validate(inp, destination.stat().st_size, reference)
    report['source'] = str(source)
    report['output'] = str(destination)
    report['expanded_byte_for_byte_match'] = True
    destination.with_suffix('.json').write_text(json.dumps(report, indent=2))
    return report

if __name__ == '__main__':
    print(json.dumps(encode(Path(sys.argv[1]), Path(sys.argv[2])), indent=2))
