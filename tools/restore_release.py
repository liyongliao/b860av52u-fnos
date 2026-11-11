#!/usr/bin/env python3
"""Reassemble release parts with streaming SHA256, never overwrite an image."""
import argparse,hashlib,json,os
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('manifest',type=Path);p.add_argument('--verify-image',type=Path);a=p.parse_args();m=json.loads(a.manifest.read_text());base=a.manifest.resolve().parent
if a.verify_image:
 h=hashlib.sha256()
 with a.verify_image.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 assert h.hexdigest()==m['image_sha256'],'Image SHA256 mismatch'
 assert a.verify_image.stat().st_size==m['image_bytes'],'Image size mismatch'
 print('Image SHA256 OK');raise SystemExit
name=m['archive'];assert Path(name).name==name
out=base/name;tmp=out.with_suffix(out.suffix+'.partial')
if out.exists() or tmp.exists():p.error('Output/partial already exists')
try:
 total=hashlib.sha256()
 with tmp.open('xb') as dst:
  for part in m['parts']:
   assert Path(part['name']).name==part['name'];src=base/part['name'];assert src.stat().st_size==part['bytes'];h=hashlib.sha256()
   with src.open('rb') as f:
    for b in iter(lambda:f.read(4*1024*1024),b''):dst.write(b);h.update(b);total.update(b)
   assert h.hexdigest()==part['sha256'],part['name']+' checksum mismatch'
   print(part['name']+' OK')
 assert total.hexdigest()==m['archive_sha256'],'Archive SHA256 mismatch'
 os.rename(tmp,out);print(str(out)+' SHA256 OK')
except BaseException:
 tmp.unlink(missing_ok=True);raise
