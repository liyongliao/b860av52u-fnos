# 线刷包与下载还原

原始镜像只在关联 [私有备份仓库](https://github.com/liyongliao/b860av52u-fnos-firmware-private/releases) 提供，需要仓库访问权限。公开项目不会暴露镜像内的主机私钥。

## 选择发布

- `emmc-v1-verified`：实机已启动的原始包，存在 data 校验超时记录。
- `emmc-v2.1-sparse`：备用优化包；相同 boot、内核、设备树、bootloader，稀疏 data 和诊断文件权限修正。仅本地验证，未再次实机烧录。

已运行的机器无需重刷。自己的原安卓线刷包是恢复安卓的路径，本项目不上传该原包。

## 分卷下载与校验

GitHub Release 单文件必须小于 2 GiB，所以镜像先无损 zstd 压缩，再分卷。[官方限制](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)。下载一个发布的所有 `.partNN`、`manifest.json` 及校验文件到同一目录。

使用 Python 3.10+ 还原分卷（按 manifest 中的顺序、逐卷校验）：

```sh
python tools/restore_release.py manifest.json
zstd -d 文件名.img.zst -o 文件名.img
```

Windows 也可用支持 zstd 的 7-Zip 解开已还原的 `.zst`。最终 IMG 的 SHA256 必须与发布中记录一致；不是对单卷直接解压或烧录。`restore_release.py` 在连接分卷后打印压缩包 SHA256，并支持 `--verify-image path.img` 校验解压结果。

## 实际烧录

1. 使用之前恢复安卓成功的 Windows USB Burning Tool 与进入烧录模式方法，导入还原出的 IMG。
2. 使用“擦除 flash / 普通擦除”，其余沿用本人成功配置；保留校验。
3. 正常完成后断电、拔掉刷机线和外接盘，接好网线和正常电源再启动。
4. 首次启动预留约 15 分钟，HDMI 未启用。访问 `http://盒子IP:5666/`，自行设置管理员。

若出现 0x30405006，保存日志，停止任务后先确认正常开机状态，不将超时直接当成校验失败或成功。此次 v1 在超时后能启动且 scrub 通过，是本次实机事实，不是所有错误都可忽略的规则。

镜像仍带原厂设备信息、上游系统文件和原临时诊断公钥。诊断不含客户端私钥，不设新增通用密码；只允许原测试 Mac，正常启动一小时后删除授权。当前已验收机器的授权已经手工清除。
