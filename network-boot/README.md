# 独立网络引导 / RAM 诊断

这个目录与线刷包分开。独立下载 [netboot-diagnostic-v1](https://github.com/liyongliao/b860av52u-fnos/releases/tag/netboot-diagnostic-v1) 的 tar.gz，展开后即可运行。它不是完整无盘 fnOS，也不安装到 eMMC。

## 包含文件

| 文件 | 作用 |
|---|---|
| artifacts/Image | 实测 6.18.18-trim ARM64 内核 |
| artifacts/diag.uimg | 实测 RAM 诊断 initramfs，网络与 eMMC 只读检查 |
| artifacts/board.dtb | v7 主线适配树 |
| artifacts/boot.img | 诊断 Android boot.img，不是持久化系统根 |
| artifacts/hybrid.dtb | 用于 bootm 验证的混合树 |
| server.py | 白名单 TFTP69 + 有界诊断接收接口 |
| init-readonly.sh | 诊断源码，读取 MMC 和只读 dm 映射 |

binary init 中保留实测网络配置，私有发行包原测试网段与源码示例 IP 不同。换网段必须重建 initramfs，不能只改服务端 IP 就认为适配完成。内核、DTB、initramfs 的来源见项目 NOTICE。诊断不含客户端 SSH 私钥。

## 服务端

Docker 将受限 UDP69 映射出来（在解压目录运行）：

```sh
docker run --rm --name b860-netboot \
 -p 69:69/udp -p 8769:8769 \
 -v "$PWD:/work:ro" -v "$PWD/logs:/logs" \
 python:3.12-alpine python /work/server.py --root /work/artifacts --logs /logs
```

普通 Linux 可用合适权限直接 `python3 server.py --root artifacts`。仅在自己的局域网使用，端口必须允许原厂 TFTP 访问；不是互联网文件服务。报告接口不能当作设备启动成败的唯一依据。

## U-Boot 手动命令（地址与本机网段需核实）

```text
setenv ipaddr 192.168.1.50
setenv serverip 192.168.1.10
setenv autostart no
setenv tftpblocksize 1468
tftpboot 0x11000000 Image
tftpboot 0x15000000 diag.uimg
tftpboot 0x01000000 board.dtb
setenv initrd_high 0x30000000
setenv bootargs console=ttyAML0,115200n8 console=tty0 mem=896M cma=128M net.ifnames=0 clk_ignore_unused pd_ignore_unused panic=20
booti 0x11000000 0x15000000 0x01000000
```

Android bootm 对照：加载 `boot.img` 到 0x01080000、`hybrid.dtb` 到 0x01000000，设置 bootargs 后 `bootm 0x01080000`。原厂地址在 trial19 实测通过。

手动内存引导本身不保存环境。使用安卓 fw_setenv 做一次性启动则**会写环境区**，不能宣传为零写入；完整历史命令见 evidence 中的报告。本仓库没有一键自动重启当前机器的脚本。

## 读取诊断结果

启动会暂用静态地址，诊断在约 90 秒后主动重启：

```sh
curl http://盒子IP:8088/emmc-diag.log
curl http://盒子IP:8088/emmc-kernel.log
```

检查两次 4 MiB 读出的字节数与哈希，而不是仅看枚举。wget POST 在本机曾段错误；日志里有 Segmentation fault 不能自动归因于 eMMC 损坏。自定义分区表没有被主线解析时，dmsetup mknodes 才能创建映射设备节点。

## 日志接口范围

原诊断 httpd 会发布 /run。此公开分发包已改为只发布两份文本日志，并移除 RAM 中的读盘样本，不提供原始数据下载；属于打包前的隐私修正，修正后的完整流程尚未再次在盒子运行。
