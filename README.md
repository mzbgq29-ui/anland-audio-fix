# Anland 原生 Wayland 音频修复

修复 Qualcomm Android 原生 V4L2 控制节点探测失败后，PipeWire / WirePlumber 卡住音频路由的问题。适用于 Anland **legacy** 音频链路，现有 KDE、GNOME、Niri、Gamescope 均可采用。

## 使用入口

- [详细修复说明与验证结果](FIX_DETAILS.md)
- [安装、验证与回退教程](INSTALL.md)
- [GitHub Actions ARM64 云编译教程](CLOUD_BUILD.md)
- [Anland 上游 PR 正文](PR_BODY.md)
- [直接下载本机验证安装包](https://github.com/mzbgq29-ui/anland-audio-fix/releases/tag/v0.1.0)
- [打开云编译 Actions](https://github.com/mzbgq29-ui/anland-audio-fix/actions)

## 修复组成

1. **Anland：**按 sysfs 身份排除 Qualcomm 摄像头控制和编解码接口，保留普通摄像头和 Anland 虚拟摄像头，并集成各桌面的打包流程。
2. **PipeWire：**SPA listener 初始化失败时清理 proxy 并返回正确错误。
3. **WirePlumber：**export 失败后结束 activation，让后续音频事件继续执行。

本机配套修补库已安装。撤掉过滤规则与恢复规则各三次 WirePlumber 重启，默认音频路由全部通过；PulseAudio 兼容应用路径也通过。完整源码回归和验证材料在 [anland-audio-PR-materials.zip](anland-audio-PR-materials.zip)。整机重启与实际摄像头捕获尚未测试。

## 版本范围

| 内容 | 基线 |
| --- | --- |
| Anland 补丁 | legacy / `a271f010b0f2ed413e193e779e38daa77070c974` |
| PipeWire 根修 | 1.6.9 |
| WirePlumber 根修 | 0.5.18 |
| 云编译安装包 | Arch Linux ARM aarch64，对应官方原版 pkgrel 1；修补版 pkgrel 1.1 |

其他发行版采用配置修复或按本发行版方式移植源码，不能直接安装 Arch 包。未修补的 WirePlumber 0.5.16 / 0.5.17 有额外回归，需要升级或确认发行版已回移相关修复。

## 云编译产物

从 Actions 成功运行的 **Artifacts** 下载 `anland-audio-archlinuxarm-aarch64`，解开 ZIP 内的 tar.gz 后包含两项修补包、官方回退包及签名、`SHA256SUMS`、完整 payload 检查结果和故障注入日志。编译采用原生 ARM64 runner 和官方 Arch Linux ARM rootfs，不需要提供密码或 Token。

本云编译构建两项底层库与配套配置，不构建完整桌面或 Android APK。重新生成包含 Anland 打包集成的新桌面软件包，可应用 `anland-audio-fix.patch` 后使用 Anland 原有 producer 构建脚本。

Anland、PipeWire、WirePlumber 的补丁分别属于各自上游。本仓库汇集补丁、构建流程和验证材料，不替代官方发行版。许可证说明见 [NOTICE.md](NOTICE.md)。
