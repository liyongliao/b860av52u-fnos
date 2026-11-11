#!/usr/bin/env python3
"""Plan a one-shot root-Android boot; --apply writes U-Boot ENV, --reboot reboots."""
import argparse,ipaddress,json,shlex,struct,zlib
from legacy_adb import call
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--host',required=True);p.add_argument('--server',required=True);p.add_argument('--adb-port',type=int,default=5555);p.add_argument('--apply',action='store_true');p.add_argument('--reboot',action='store_true');a=p.parse_args()
for v in (a.host,a.server):ipaddress.IPv4Address(v)
if a.reboot and not a.apply:p.error('--reboot requires --apply')
args='console=ttyAML0,115200n8 console=tty0 no_console_suspend mem=896M cma=128M net.ifnames=0 clk_ignore_unused pd_ignore_unused panic=20'
bootcmd='setenv bootcmd bootsys; setenv fnnas_stage entered; if saveenv; then run fnnas_once; fi; run storeargs; bootsys'
once=f'setenv ipaddr {a.host}; setenv serverip {a.server}; setenv autostart no; setenv tftpblocksize 1468; '
once+=f'if tftpboot 0x11000000 {a.server}:Image; then if tftpboot 0x15000000 {a.server}:diag.uimg; then if tftpboot 0x01000000 {a.server}:board.dtb; then '
once+=f'setenv fnnas_stage kernel_handoff; if saveenv; then setenv initrd_high 0x30000000; setenv bootargs {args}; booti 0x11000000 0x15000000 0x01000000; fi; fi; fi; fi; '
once+='setenv initrd_high; run storeargs; reset'
print(json.dumps({'host':a.host,'bootcmd':bootcmd,'fnnas_once':once,'writes_env':a.apply,'reboots':a.reboot},indent=2))
if not a.apply:raise SystemExit
address=(a.host,a.adb_port)
current=call('shell:fw_printenv bootcmd',address,timeout=15).decode()
if 'bootcmd=bootsys' not in current.splitlines():raise RuntimeError('Refusing to replace a non-default bootcmd')
for key,value in [('fnnas_once',once),('bootcmd',bootcmd)]:
 result=call('shell:fw_setenv '+key+' '+shlex.quote(value),address,timeout=20).decode()
 if 'successful' not in result:raise RuntimeError('ENV write did not report success')
env=bytes.fromhex(call('shell:/system/xbin/busybox od -An -v -tx1 -N65536 /dev/block/env',address,timeout=20).decode())
assert len(env)==65536 and struct.unpack_from('<I',env)[0]==zlib.crc32(env[4:])
values=dict(x.split(b'=',1) for x in env[4:].split(b'\0\0',1)[0].split(b'\0') if b'=' in x)
assert values[b'bootcmd']==bootcmd.encode() and values[b'fnnas_once']==once.encode()
print('One-shot ENV verified; next boot restores bootsys before attempting TFTP.')
if a.reboot:
 try:call('shell:/system/xbin/busybox sync; reboot',address,timeout=5)
 except (TimeoutError,EOFError,ConnectionResetError):pass
