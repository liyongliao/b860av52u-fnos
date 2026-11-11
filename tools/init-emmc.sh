#!/bin/sh
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
mkdir -p /proc /sys /dev /run /newroot
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
mount -t tmpfs tmpfs /run
exec > /run/b860-early-boot.log 2>&1
echo 'B860AV5.2-U fnOS eMMC loader v1'
uname -a
cat /proc/cmdline
fail() {
    echo "BOOT STOPPED: $*"
    dmesg > /run/b860-kernel.log
    ip link set lo up
    ip link set eth0 up
    ip addr add 192.168.1.50/24 dev eth0
    httpd -p 8088 -h /run
    while :; do sleep 60; done
}
emmc=
attempt=0
while [ "$attempt" -lt 20 ]; do
    for entry in /sys/block/mmcblk[0-9]; do
        [ -f "$entry/device/type" ] || continue
        [ "$(cat "$entry/device/type")" = MMC ] || continue
        [ "$(cat "$entry/device/name")" = 05S000 ] || continue
        [ "$(cat "$entry/size")" = 15335424 ] || continue
        emmc=/dev/${entry##*/}
    done
    [ -n "$emmc" ] && break
    sleep 1
    attempt=$((attempt + 1))
done
[ -n "$emmc" ] || fail 'Expected 05S000 7.31GiB eMMC not found'
insmod /lib/modules/dm-mod.ko || fail 'Cannot load device mapper'
mkdir -p /dev/mapper
dmsetup create fnos-root --noudevsync --uuid B860-FNOS-ROOT --table "0 10485760 linear $emmc 4456448" || fail 'Cannot map original data partition'
dmsetup mknodes --noudevsync fnos-root || fail 'Cannot create root block device'
[ -b /dev/mapper/fnos-root ] || fail 'Root block device absent'
dmsetup table fnos-root
identity=$(blkid /dev/mapper/fnos-root)
echo "$identity"
echo "$identity" | grep -q 'UUID="e8413606-5135-4b76-a0a1-284e9c7985a8"' || fail 'fnOS filesystem UUID mismatch'
mount -t btrfs -o rw,noatime,compress=zstd:1 /dev/mapper/fnos-root /newroot || fail 'Cannot mount fnOS filesystem'
[ -x /newroot/lib/systemd/systemd ] || fail 'Missing system manager'
mkdir -p /newroot/run /newroot/proc /newroot/sys /newroot/dev
echo 'fnOS root filesystem mounted; starting system manager'
mount --move /proc /newroot/proc
mount --move /sys /newroot/sys
mount --move /dev /newroot/dev
mount --move /run /newroot/run
exec switch_root /newroot /sbin/init
