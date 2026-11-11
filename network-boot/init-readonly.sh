#!/bin/sh
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
mkdir -p /proc /sys /dev /run
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
mkdir -p /run
mount -t tmpfs tmpfs /run
exec > /run/emmc-diag.log 2>&1
echo 'B860 RAM-only eMMC read diagnostic'
uname -a
cat /proc/cmdline
ip link set lo up
ip link set eth0 up
ip addr add 192.168.31.29/24 dev eth0
ip route add default via 192.168.31.1
sleep 3
ip addr show eth0
ping -c 2 -W 1 192.168.31.225
cat /proc/partitions
mkdir -p /sys/kernel/debug
mount -t debugfs debugfs /sys/kernel/debug
for f in /sys/kernel/debug/mmc*/ios; do echo "$f"; cat "$f"; done
for dev in /sys/block/mmcblk[0-9]; do
    [ -f "$dev/size" ] || continue
    echo "EMMC $dev"
    cat "$dev/size" "$dev/device/name" "$dev/device/type"
    block=/dev/${dev##*/}
    echo "READ CHECK 1 $block"
    timeout 20 dd if="$block" of=/run/mmc-sample.bin bs=1048576 count=4
    wc -c /run/mmc-sample.bin
    sha256sum /run/mmc-sample.bin
    echo "READ CHECK 2 $block"
    timeout 20 dd if="$block" of=/run/mmc-sample.bin bs=1048576 count=4
    wc -c /run/mmc-sample.bin
    sha256sum /run/mmc-sample.bin
    if [ "$(cat "$dev/size")" = 15335424 ]; then
        insmod /lib/modules/dm-mod.ko
        mkdir -p /dev/mapper
        dmsetup create fnos-probe --readonly --noudevsync --table "0 10485760 linear $block 4456448"
        dmsetup mknodes --noudevsync fnos-probe
        dmsetup table fnos-probe
        timeout 20 dd if=/dev/mapper/fnos-probe of=/run/data-sample.bin bs=1048576 count=4
        wc -c /run/data-sample.bin
        sha256sum /run/data-sample.bin
        dmsetup remove --noudevsync fnos-probe
    fi
done
dmesg > /run/emmc-kernel.log
cat /proc/uptime
echo 'No eMMC writes performed'
wget -T 10 -O /run/report-result --post-file=/run/emmc-diag.log http://192.168.31.225:8769/diag
wget -T 10 -O /run/report-result --post-file=/run/emmc-kernel.log http://192.168.31.225:8769/kernel
mkdir -p /run/public
cp /run/emmc-diag.log /run/emmc-kernel.log /run/public/
rm -f /run/mmc-sample.bin /run/data-sample.bin
httpd -p 8088 -h /run/public
sleep 90
reboot -f
while :; do sleep 60; done
