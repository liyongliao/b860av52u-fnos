# 来源与授权范围

这是用户自有设备的适配记录，不是飞牛官方机型固件。

- [ophub/fnnas](https://github.com/ophub/fnnas)：上游镜像和适配资料；实测来源镜像 `fnnas_amlogic_s905l3b_k6.18.18_2026.09.23.img.gz`。
- Linux / DTS / 设备驱动归原作者，遵循其原始许可证；设备树来源是上游镜像及用户原厂固件，不能统一改授其他许可证。
- fnOS 用户空间、厂商 bootloader 和 USB 引导组件归各自权利人。本仓库未重新授权这些二进制；Release 仅作为本人的私有设备备份。
- 容器格式、稀疏格式判断参照 [Amlogic U-Boot 源码](https://android.googlesource.com/platform/external/u-boot/+/refs/heads/android-tv-s-beta3/drivers/usb/gadget/v2_burning/)。这是相近公开源码；报告明确区分了公开源码推断与原机 BL33 反汇编验证。
- 不包含原安卓整包、客户端 SSH 私钥、账号密码、GitHub 凭据、环境分区备份或个人授权密钥。

线刷镜像沿用了原厂设备配置与上游系统文件，也含原临时诊断公钥（没有客户端私钥）。原系统自身的 SSH 主机密钥不等于用户客户端密钥。不要将本人的私有备份未经清理直接公开分发。
