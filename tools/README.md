# 工具与重建边界

Python 3.10+，DTB 编译需 dtc。脚本只操作指定本地文件，不连接盒子。

```sh
python tools/aml_v2_pack.py inspect original.img
python tools/android_sparse.py rootfs-5g.btrfs rootfs.sparse
python tools/aml_v2_pack.py repack original.img output.img \
 --replace PARTITION:boot=boot.img --replace dtb:meson1=hybrid.dtb \
 --add PARTITION:data=rootfs.sparse
```

- `aml_v2_pack.py`：Amlogic v2 容器 CRC 与每项 VERIFY；原包重封装曾逐字节一致。修改 sparse 时的 SHA1 是 sparse 文件表示，不是展开文件 SHA1。
- `android_sparse.py`：只接受 RAW/FILL0、4096 字节块、每 chunk 最多 8 MiB，不使用 DONT_CARE/CRC32 chunk；展开后逐字节比较输入。FILL0 实际烧录依赖普通擦除；设备校验只读每 FILL 首字。
- `build_boot.py`：显式指定内核/initramfs/DTB，构建 Android v0 boot.img，最大 32 MiB。它不自行编译内核或飞牛用户空间。
- `init-emmc.sh`：已用过的早期挂根逻辑，校验 MMC 型号/容量与根 UUID。
- `restore_release.py`：分卷还原与 SHA256 检查。

完整复现还需要自己的原安卓包、相同上游根系统、内核模块及最小 initramfs 的构建环境。本仓库没有声称提供 fnOS 或厂商固件的完整可再发行源码，也不把未发布的 v3 RAM-SSH 试验纳入工作方案。
