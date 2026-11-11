#!/usr/bin/env python3
import argparse,gzip,hashlib,struct
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--kernel',type=Path,required=True);p.add_argument('--ramdisk',type=Path,required=True);p.add_argument('--dtb',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
if a.output.exists():p.error('Output exists')
k=gzip.compress(a.kernel.read_bytes(),compresslevel=6,mtime=0);r=a.ramdisk.read_bytes();d=a.dtb.read_bytes()
assert r[:2]==b'\x1f\x8b' and d[:4]==bytes.fromhex('d00dfeed')
h=bytearray(2048);h[:8]=b'ANDROID!';struct.pack_into('<10I',h,8,len(k),0x1080000,len(r),0x1000000,len(d),0xf00000,0x100,2048,0,0)
h[48:64]=b'B860-FNOS-eMMC'.ljust(16,b'\0')
s=b'console=ttyAML0,115200n8 console=tty0 no_console_suspend mem=896M cma=128M net.ifnames=0 clk_ignore_unused pd_ignore_unused panic=20 root=/dev/mapper/fnos-root rootfstype=btrfs rw';h[64:64+len(s)]=s
sha=hashlib.sha1()
for x in (k,r,d):sha.update(x);sha.update(struct.pack('<I',len(x)))
h[576:596]=sha.digest();data=bytes(h)+b''.join(x+bytes(-len(x)%2048) for x in (k,r,d));assert len(data)<=32*1024*1024
a.output.write_bytes(data);print(hashlib.sha256(data).hexdigest())
