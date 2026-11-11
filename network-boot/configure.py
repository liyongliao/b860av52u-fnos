#!/usr/bin/env python3
"""Configure a COPY of the downloaded network diagnostic artifacts; no device access."""
import argparse,gzip,ipaddress,re,struct,zlib,hashlib,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent/'artifacts')
p.add_argument('--ip',required=True);p.add_argument('--server',required=True);p.add_argument('--gateway',required=True);p.add_argument('--mac',help='Optional target MAC, needs fdtput from dtc')
a=p.parse_args()
for v in (a.ip,a.server,a.gateway):ipaddress.IPv4Address(v)
if a.mac:
 mac=a.mac.split(':');assert len(mac)==6 and all(len(x)==2 for x in mac)
 for name in ('board.dtb','hybrid.dtb'):subprocess.run(['fdtput','-t','bx',str(a.root/name),'/soc/ethernet@c9410000','local-mac-address',*mac],check=True)
u=a.root/'diag.uimg';old=u.read_bytes();raw=gzip.decompress(old[64:]);off=0;out=bytearray();found=False
while off<len(raw) and raw[off:off+6]==b'070701':
 f=[int(raw[off+6+i*8:off+14+i*8],16) for i in range(13)];ns=f[11];name=raw[off+110:off+110+ns-1];start=(off+110+ns+3)//4*4;data=raw[start:start+f[6]];off=(start+f[6]+3)//4*4
 if name==b'init':
  s=data.decode();s=re.sub(r'ip addr add [0-9.]+/24 dev eth0','ip addr add '+a.ip+'/24 dev eth0',s);s=re.sub(r'ip route add default via [0-9.]+','ip route add default via '+a.gateway,s);s=re.sub(r'ping -c 2 -W 1 [0-9.]+','ping -c 2 -W 1 '+a.server,s);s=re.sub(r'http://[0-9.]+:8769/','http://'+a.server+':8769/',s);data=s.encode();found=True
 f[6]=len(data);out+=b'070701'+''.join(f'{i:08x}' for i in f).encode()+name+b'\0';out+=bytes(-len(out)%4);out+=data;out+=bytes(-len(out)%4)
 if name==b'TRAILER!!!':break
assert found;out+=bytes(-len(out)%512);payload=gzip.compress(bytes(out),mtime=0);h=bytearray(old[:64]);struct.pack_into('>I',h,4,0);struct.pack_into('>I',h,12,len(payload));struct.pack_into('>I',h,24,zlib.crc32(payload));struct.pack_into('>I',h,4,zlib.crc32(h));u.write_bytes(h+payload)
b=a.root/'boot.img';old=b.read_bytes();ks,ka,rs,ra,ds,da,tags,page=struct.unpack_from('<8I',old,8);ro=page+((ks+page-1)//page)*page;k=old[page:page+ks];dt=(a.root/'hybrid.dtb').read_bytes();h=bytearray(old[:page]);struct.pack_into('<I',h,16,len(payload));struct.pack_into('<I',h,24,len(dt));s=hashlib.sha1()
for d in (k,payload,dt):s.update(d);s.update(struct.pack('<I',len(d)))
h[576:596]=s.digest();image=h+b''.join(d+bytes(-len(d)%page) for d in (k,payload,dt));assert len(image)<=32*1024*1024;b.write_bytes(image)
print('Configured diagnostics for '+a.ip+'/24; update U-Boot addresses to match. No device contacted.')
