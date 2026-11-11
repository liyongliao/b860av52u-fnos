#!/usr/bin/env python3
"""Build an offline DTB candidate; no flash or device access.

Keep the tested mainline tree and add only bootloader-visible vendor metadata.
Requires dtc. This candidate is NOT a claim of bootm or burn compatibility.
"""
import difflib
import hashlib
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
BASE = HERE / 'b860-emmc-v7.dts'
VENDOR = HERE / 'vendor-board-1g.dts'


def block(text, name, level=1):
    match = re.search(r'^' + '\t' * level + r'(?:[\w_]+: )?' + re.escape(name) + r' \{', text, re.M)
    if not match:
        raise ValueError('Missing node ' + name)
    depth = 0
    for end in range(text.index('{', match.start()), len(text)):
        if text[end] == '{': depth += 1
        if text[end] == '}':
            depth -= 1
            if not depth:
                return match.start(), end + 2, text[match.start():end + 2]
    raise ValueError('Unterminated node ' + name)


def vendor_metadata(text, name):
    node = block(text, name)[2]
    # Vendor numeric phandles overlap the unrelated mainline clock/GPIO handles.
    node = re.sub(r'(?m)^(\s*)\w+: ', r'\1', node)
    node = re.sub(r'(?m)^(\s*)(phandle|part-\d+|key\d+|unifykey-index-\d+|memory-region) = <(0x[0-9a-f]+)>;',
                  lambda m: f'{m[1]}{m[2]} = <0x{int(m[3], 16) + 0x1000:x}>;', node)
    if name != 'partitions':
        if re.search(r'^\t\tstatus = ', node, re.M):
            node = re.sub(r'^\t\tstatus = .*;', '\t\tstatus = "disabled";', node, flags=re.M)
        else:
            node = node.replace('{', '{\n\t\tstatus = "disabled";', 1)
    if name == 'vpu':
        # Bootloader consumes clk_level. Linux clocks refer to another tree.
        node = re.sub(r'^\t\t(?:clocks|clock-names) = .*;\n', '', node, flags=re.M)
    return node


def main():
    original = BASE.read_text()
    vendor = VENDOR.read_text()
    result = original.replace('model = "B860AV5.2-U internal eMMC legacy 20MHz diagnostic";',
                              'model = "B860AV5.2-U fnOS eMMC bootm hybrid candidate v1";\n'
                              '\tamlogic-dt-id = "gxlx3_az201_1g";')
    assert result != original
    # U-Boot's rsvmem command uses these exact paths, not phandle lookup.
    result = result.replace('secmon_reserved_alt: secmon@5000000 {',
                            'secmon_reserved_alt: linux,secmon {\n'
                            '\t\t\tcompatible = "amlogic, aml_secmon_memory";')
    result = result.replace('secmon_reserved_bl32: secmon@5300000 {',
                            'secmon_reserved_bl32: linux,secos {\n'
                            '\t\t\tcompatible = "amlogic, aml_secos_memory";')
    result = result.replace('"/reserved-memory/secmon@5000000"', '"/reserved-memory/linux,secmon"')
    result = result.replace('"/reserved-memory/secmon@5300000"', '"/reserved-memory/linux,secos"')
    # The stock arch fixup checks literal /memory; avoid a second memory node.
    result = result.replace('\tmemory@0 {', '\tmemory {')
    reserved_start, reserved_end, _ = block(result, 'reserved-memory')
    result = result[:reserved_end - 2] + '''

		linux,meson-fb {
			reg = <0x00 0x3f800000 0x00 0x800000>;
			no-map;
			phandle = <0x105a>;
		};
	''' + result[reserved_end - 2:]
    metadata = '\n\n'.join(vendor_metadata(vendor, n) for n in
                            ('partitions', 'efusekey', 'unifykey', 'vpu', 'meson-fb'))
    metadata += '''

	secmon {
		compatible = "amlogic, secmon";
		status = "disabled";
		memory-region = <0x42>;
		in_base_func = <0x82000020>;
		out_base_func = <0x82000021>;
		reserve_mem_size = <0x300000>;
	};
'''
    end = result.rfind('};')
    result = result[:end] + '\n' + metadata + result[end:]
    dts = HERE / 'b860-emmc-hybrid-v1.dts'
    dtb = HERE / 'b860-emmc-hybrid-v1.dtb'
    dts.write_text(result)
    (HERE / 'b860-emmc-hybrid-v1.diff').write_text(''.join(difflib.unified_diff(
        original.splitlines(True), result.splitlines(True), fromfile=str(BASE), tofile=str(dts))))
    proc = subprocess.run(['dtc', '-I', 'dts', '-O', 'dtb', '-p', '16384', '-o', str(dtb), str(dts)],
                          capture_output=True, text=True)
    (HERE / 'b860-emmc-hybrid-v1.dtc.log').write_text(proc.stderr)
    proc.check_returncode()
    # Roundtrip is an independent parser and catches duplicate phandles.
    decoded = subprocess.run(['dtc', '-I', 'dtb', '-O', 'dts', str(dtb)], capture_output=True, text=True, check=True).stdout
    (HERE / 'b860-emmc-hybrid-v1.decoded.dts').write_text(decoded)
    handles = re.findall(r'^\s+phandle = <(0x[0-9a-f]+)>;', decoded, re.M)
    assert len(handles) == len(set(handles)), 'duplicate phandles'
    # Every tested mainline hardware subtree remains byte-for-byte identical.
    for name in ('soc', 'cpus', 'thermal-zones', 'scpi', 'aliases', 'chosen'):
        assert block(original, name)[2] == block(result, name)[2], name
    # Partition sizes, flags, order, and names unchanged; normalize handles.
    oldparts = block(vendor, 'partitions')[2]
    newparts = block(result, 'partitions')[2]
    for name in ('conf', 'logo', 'recovery', 'rsv', 'tee', 'crypt', 'misc', 'boot', 'system', 'env', 'cache', 'data'):
        old = block(oldparts, name, 2)[2]
        new = block(newparts, name, 2)[2]
        for prop in ('pname', 'size', 'mask'):
            pat = re.compile(r'\b' + prop + r' = ([^;]+);')
            assert pat.search(old)[1] == pat.search(new)[1], (name, prop)
    report = dict(base_sha256=hashlib.sha256(BASE.read_bytes()).hexdigest(),
                  vendor_sha256=hashlib.sha256(VENDOR.read_bytes()).hexdigest(),
                  candidate_sha256=hashlib.sha256(dtb.read_bytes()).hexdigest(),
                  dtb_size=dtb.stat().st_size, mainline_hardware_subtrees_unchanged=True,
                  vendor_partition_order_sizes_masks_unchanged=True, unique_phandles=True,
                  validated_on_device=False, bootm_validated=False,
                  runtime_unknowns=['Vendor early board initialization may read additional undocumented DTB nodes.',
                                    'rsvmem fixup writes depend on live secure firmware registers.',
                                    'USB Burning Tool acceptance and bootm path need device validation.'])
    (HERE / 'b860-emmc-hybrid-v1.validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
