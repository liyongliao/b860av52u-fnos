#!/usr/bin/env python3
"""Offline, streaming Amlogic V2 container inspector/repacker.

This manipulates the *container*, not the boot protocol or device partitions.
Raw and strictly checked Android sparse RAW/FILL0 partition items are supported.
Sparse VERIFY hashes the sparse file representation, as stock U-Boot does.
No device access, flash command, or automatic target execution is implemented.

Layout: Amlogic amlImage_if.h, ItemInfo_V2 / AmlFirmwareImg_t (pack 4).
CRC and VERIFY conventions are corroborated against the supplied stock image.
"""
from __future__ import annotations
import argparse
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import struct
import zlib
from android_sparse import validate as validate_sparse

HEADER = struct.Struct('<IIIQII36s')
ITEM = struct.Struct('<IIQQQ256s256s32s')
CHUNK = 4 * 1024 * 1024
MAGIC = 0x27B51956


@dataclasses.dataclass
class Entry:
    index: int
    file_type: int
    cursor: int
    offset: int
    size: int
    main_bytes: bytes
    sub_bytes: bytes
    reserved: bytes
    source: Path
    source_offset: int
    inline: bytes | None = None

    @property
    def main(self): return self.main_bytes.split(b'\0', 1)[0].decode('ascii')
    @property
    def sub(self): return self.sub_bytes.split(b'\0', 1)[0].decode('ascii')
    @property
    def key(self): return f'{self.main}:{self.sub}'

    def chunks(self):
        if self.inline is not None:
            yield self.inline
            return
        with self.source.open('rb') as stream:
            stream.seek(self.source_offset)
            left = self.size
            while left:
                block = stream.read(min(CHUNK, left))
                if not block:
                    raise ValueError(f'Truncated payload {self.key}')
                left -= len(block)
                yield block

    def digest(self, algorithm='sha256'):
        h = hashlib.new(algorithm)
        for block in self.chunks(): h.update(block)
        return h.hexdigest()


def container_crc(path):
    crc = 0
    with path.open('rb') as stream:
        stream.seek(4)
        while block := stream.read(CHUNK): crc = zlib.crc32(block, crc)
    return crc ^ 0xFFFFFFFF


def read_image(path: Path, check_crc=True):
    with path.open('rb') as stream:
        raw = stream.read(HEADER.size)
        crc, version, magic, size, alignment, count, reserved = HEADER.unpack(raw)
        if version != 2 or magic != MAGIC or size != path.stat().st_size:
            raise ValueError('Not a complete supported Amlogic V2 image')
        if alignment not in (4, 16, 512, 4096):
            raise ValueError(f'Unexpected item alignment {alignment}')
        if count > 10000 or HEADER.size + count * ITEM.size > size:
            raise ValueError('Invalid item count')
        entries = []
        for i in range(count):
            fields = ITEM.unpack(stream.read(ITEM.size))
            e = Entry(*fields, source=path, source_offset=fields[3])
            if e.index != i or e.offset < HEADER.size + count * ITEM.size or e.offset + e.size > size:
                raise ValueError(f'Invalid descriptor {i}')
            if e.offset % alignment:
                raise ValueError(f'Unaligned payload {e.key}')
            entries.append(e)
    if len({e.key for e in entries}) != len(entries):
        raise ValueError('Duplicate item keys require explicit duplicate handling')
    if check_crc and container_crc(path) != crc:
        raise ValueError('Container CRC mismatch')
    return dict(crc=crc, version=version, magic=magic, size=size, alignment=alignment,
                count=count, reserved=reserved), entries


def verify(path: Path):
    header, entries = read_image(path)
    by_key = {e.key: e for e in entries}
    checks = []
    for e in entries:
        if e.main != 'VERIFY': continue
        partition = by_key.get('PARTITION:' + e.sub)
        if partition is None or partition.file_type not in (0, 0xfe):
            raise ValueError(f'Cannot validate VERIFY target {e.sub}')
        if partition.file_type == 0xfe:
            with path.open('rb') as stream:
                stream.seek(partition.offset)
                validate_sparse(stream, partition.size)
        expected = b'sha1sum ' + partition.digest('sha1').encode('ascii')
        actual = b''.join(e.chunks())
        if actual != expected:
            raise ValueError(f'VERIFY mismatch for {e.sub}')
        checks.append(e.sub)
    return dict(path=str(path.resolve()), size=header['size'], version=2,
                item_count=header['count'], alignment=header['alignment'],
                crc=f'0x{header["crc"]:08x}', crc_valid=True,
                partition_sha1_verified=checks,
                items=[dict(key=e.key, file_type=e.file_type, offset=e.offset,
                            size=e.size, reserved_hex=e.reserved.hex()) for e in entries])


def parse_spec(spec):
    key, filename = spec.split('=', 1)
    main, sub = key.split(':', 1)
    if not main or not sub or len(main.encode('ascii')) >= 256 or len(sub.encode('ascii')) >= 256:
        raise ValueError(f'Invalid item key {key}')
    path = Path(filename).resolve()
    if not path.is_file(): raise ValueError(f'Missing payload {path}')
    with path.open('rb') as stream:
        if stream.read(4) == bytes.fromhex('3aff26ed'):
            if main != 'PARTITION': raise ValueError('Sparse format is only valid for PARTITION items')
            stream.seek(0)
            validate_sparse(stream, path.stat().st_size)
    return key, path

def file_type(path):
    with path.open('rb') as stream:
        return 0xfe if stream.read(4) == bytes.fromhex('3aff26ed') else 0


def raw_entry(key, path, *, verify_partition=True):
    main, sub = key.split(':', 1)
    reserved = bytes([1 if main == 'PARTITION' and verify_partition else 0]) + bytes(31)
    return Entry(0, file_type(path), 0, 0, path.stat().st_size,
                 main.encode().ljust(256, b'\0'), sub.encode().ljust(256, b'\0'),
                 reserved, path, 0)


def build(source: Path, output: Path, replacements, additions):
    if source.resolve() == output.resolve(): raise ValueError('Refusing in-place modification')
    if output.exists(): raise ValueError('Output already exists')
    header, entries = read_image(source)
    if any(e.file_type not in (0, 0xfe) for e in entries):
        raise ValueError('Unsupported source item type')
    by_key = {e.key: e for e in entries}
    edited = set()
    for spec in replacements:
        key, path = parse_spec(spec)
        if key not in by_key: raise ValueError(f'Replacement target absent: {key}')
        old = by_key[key]
        new = dataclasses.replace(old, source=path, source_offset=0, size=path.stat().st_size, file_type=file_type(path))
        entries[entries.index(old)] = new
        by_key[key] = new
        edited.add(key)
    for spec in additions:
        key, path = parse_spec(spec)
        if key in by_key: raise ValueError(f'Addition already exists: {key}')
        new = raw_entry(key, path)
        entries.append(new)
        by_key[key] = new
        edited.add(key)
    for key in sorted(edited):
        main, sub = key.split(':', 1)
        if main != 'PARTITION': continue
        partition = by_key[key]
        check_key = 'VERIFY:' + sub
        payload = b'sha1sum ' + partition.digest('sha1').encode('ascii')
        old_check = by_key.get(check_key)
        if old_check:
            check = dataclasses.replace(old_check, size=48, inline=payload)
            entries[entries.index(old_check)] = check
        else:
            check = raw_entry(check_key, source)
            check = dataclasses.replace(check, size=48, inline=payload)
            entries.insert(entries.index(partition) + 1, check)
        by_key[check_key] = check
        partition.reserved = bytes([1]) + partition.reserved[1:]
    alignment = header['alignment']
    offset = HEADER.size + ITEM.size * len(entries)
    for index, e in enumerate(entries):
        e.index = index
        offset = (offset + alignment - 1) // alignment * alignment
        e.offset = offset
        offset += e.size
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_name(output.name + '.partial')
    if tmp.exists(): raise ValueError('Partial output already exists')
    try:
        with tmp.open('xb') as stream:
            stream.write(HEADER.pack(0, 2, MAGIC, offset, alignment, len(entries), header['reserved']))
            for e in entries:
                stream.write(ITEM.pack(e.index, e.file_type, e.cursor, e.offset, e.size,
                                       e.main_bytes, e.sub_bytes, e.reserved))
            for e in entries:
                stream.write(bytes(e.offset - stream.tell()))
                for block in e.chunks(): stream.write(block)
            assert stream.tell() == offset
        crc = container_crc(tmp)
        with tmp.open('r+b') as stream: stream.write(struct.pack('<I', crc))
        result = verify(tmp)
        os.rename(tmp, output)
        result['path'] = str(output.resolve())
        return result
    except BaseException:
        if tmp.exists(): tmp.unlink()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    inspect = commands.add_parser('inspect')
    inspect.add_argument('image', type=Path)
    repack = commands.add_parser('repack')
    repack.add_argument('image', type=Path)
    repack.add_argument('output', type=Path)
    repack.add_argument('--replace', action='append', default=[], metavar='MAIN:SUB=FILE')
    repack.add_argument('--add', action='append', default=[], metavar='MAIN:SUB=FILE')
    args = parser.parse_args()
    result = verify(args.image) if args.command == 'inspect' else build(args.image, args.output, args.replace, args.add)
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
