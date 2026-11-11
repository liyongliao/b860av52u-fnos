# 适配机制

## 保留原引导与分区

原厂 Amlogic 自定义分区表，512 字节扇区。本次实际记录：

| 区域 | 起始扇区 | 扇区数 |
|---|---:|---:|
| boot | 2260992 | 65536 |
| system | 2342912 | 2097152 |
| data | 4456448 | 10878976 |

32 MiB boot 装 Android v0 boot.img。根映射长度固定 10485760 扇区（5 GiB），从 data 起点开始，容量小于 data 分区。

```sh
dmsetup create fnos-root --noudevsync --uuid B860-FNOS-ROOT \
  --table '0 10485760 linear /dev/mmcblk2 4456448'
dmsetup mknodes --noudevsync fnos-root
```

这不是可任意复制执行的重分区命令：先确认板型、MMC 名称和总扇区数。`tools/init-emmc.sh` 做对应身份检查。关闭通用 resize-rootfs，不运行 fnnas-tf 重写本机布局。

## 设备树

`device-tree/b860-emmc-v7.dts`：已验证的主线最小硬件树 + fixed100 网卡 + eMMC legacy20MHz。

`b860-emmc-hybrid-v1.dts`：在其上保留厂商 /partitions 与 U-Boot 必需元数据，重映射 phandle，提供 rsvmem 固定路径和安全保留。厂商显示节点只供引导读取，Linux 图形未启用。保守保留区域有重叠警告，当前实机能启动；不宣称已清理所有设备树告警。

## 引导顺序

1. 原厂 ROM/DDR/BL33，保持原 bootloader。
2. 默认 bootsys 读 Android boot.img，gzip 内核在 64 MiB 解压上限以内。
3. 优先使用 dtbpart 混合树；second 仅为回退。
4. 最小 initramfs 加载 dm-mod，检查 eMMC 身份，映射 data、验证 UUID、挂 Btrfs。
5. switch_root 到原飞牛用户空间，服务初始化后通过 5666 管理。

来源报告在 evidence。完整根用户空间不是本仓库自行编译；使用上游镜像。备用包不会自行更新已烧录机器。
