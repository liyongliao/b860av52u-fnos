# eMMC 适配调整组件 v1

这些是已成功启动的原始 v1 boot.img、最小 initramfs、hybrid DTB 和打包工具。不是完整线刷 IMG，不包含飞牛根文件系统、原厂 bootloader、SSH 主机私钥或客户端授权。

配套板型：B860AV5.2-U / gxlx3_az201_1g，1GB RAM、05S000 eMMC。boot 区32MiB；root在data起始扇区4456448、长度10485760扇区，根UUID e8413606-5135-4b76-a0a1-284e9c7985a8。根Btrfs必须已正确准备为5GiB，关闭自动扩分区，不可任意套用到其他布局。

boot.img 使用 Android v0 格式、gzip内核6.18.18-trim。必须同时更新原厂 dtb:meson1 项（dtbpart），仅换 boot.img second 不足。需要自行提供合法原厂包与上游根系统；tools 中容器工具只修改本地指定输入，不自动刷设备。

DTB中的MAC保留原实测设备配置，其他设备应修改MAC并重新构建boot.img/DTB配套。网络引导单独在netboot-diagnostic-v1，不与这个根系统挂载入口混用。

当前实机数据2.43GiB scrub通过、fnOSV1.1.31网页可用。HDMI/WiFi等没有适配。来源与授权见公开项目NOTICE；不是官方机型固件。

项目：https://github.com/liyongliao/b860av52u-fnos
