# 详细修复说明与验证报告

日期：2026-10-13；平台：Arch Linux ARM aarch64、Niri Anland legacy、普通会话用户 UID 1000。

## 原因与修复

原生高通摄像头控制节点在 SPA listener 初始化时返回 EALREADY。PipeWire 1.6.9 忽略错误，WirePlumber 0.5.18 等待永远不能绑定的 proxy，使后续音频路由事件无法完成。两项配套补丁修复错误传播与 activation 结束；Anland 规则提前排除这些已知控制／编解码接口。

## 真实会话

最终安装并测试的是 `libpipewire 1:1.6.9-1.1`、`libwireplumber 0.5.18-1.1`。源代码版本仍分别是 1.6.9、0.5.18，本地 pkgrel 用于区分修补包。

| 场景 | 次数 | 结果 |
| --- | --- | --- |
| 仅精准规则、未安装底层补丁 | 3 次重启 WirePlumber | 默认原生 PipeWire 播放流自动连接扬声器 |
| 已安装成对底层补丁、临时撤掉规则 | 3 次重启 WirePlumber | 原生设备初始化仍失败，但不会卡音频，立体声两条 links active |
| 成对底层补丁、恢复规则 | 3 次重启 WirePlumber | 默认路由及两条 active links 全部成功 |
| PulseAudio 兼容应用 | 1 个播放流 | 不指定输出目标，自动连接 anland-speaker |

无规则时真实 journal 记录了 `/dev/video0`、`/dev/video1` 的 EALREADY 和已经结束的 V4L2 activation 错误。恢复规则后四个匹配节点均记录为 disabled。这直接验证了底层根修，也验证了过滤规则在初始化前生效。

每次重启后 `anland-mic`、`anland-camera-0`、`anland-camera-1` 均存在。最终三个音频服务 active；WirePlumber 已加载安装位置的两项修补库；已安装 ELF 与验证过的包内 ELF 的 SHA256 一致，临时模块路径环境变量已移除。

证据：

- `validation/installed-rootfix-validation.json`
- `validation/installed-rootfix-wireplumber.log`
- `validation/pulse-route-validation.json`
- `validation/installed-library-validation.json`

## 故障注入及源码回归

- PipeWire：EALREADY／EIO／ENOMEM，各测试未注册 listener 和部分注册后失败，共六项；全部错误正确传播、listener 清理；正常设备仍能 BOUND。
- WirePlumber：不存在的临时 V4L2 路径，main context 和 threaded client context 均及时返回 activation 错误、没有 proxy／活动 feature；随后 core 请求继续完成。
- 原版／单边修补／成对修补四组对照分别复现等待、等待、NULL 断言、成功错误回调。
- WirePlumber 六个相关上游套件通过：core、events、object-manager、proxy、transition、client-context。
- 将最终已安装的两个库再交给可移植隔离运行器，PipeWire、WirePlumber 回归均通过。证据位于 `validation/installed-pair-isolated/`。
- Anland 11 项回归通过；最终 9 项打包／安装集成检查通过；19 文件完整 patch 已通过干净基线 apply-check 及 diff-check。

## 打包检查

官方原版包的 Arch Linux ARM Build System 签名验证通过。两个本地包分别保留 358／61 个 payload 条目；仅目标 ELF 的内容变化，其他文件、链接及条目元数据与原版一致。依赖和 SONAME 保留，并提供原精确版本的兼容关系，使现有 PipeWire／WirePlumber split 包依赖仍满足。

真实启动检查发现第一版库的默认构建 prefix 为 `/usr/local`，造成模块查找失败。该版本已替换：最终库按 `/usr`、`/etc`、`/var` 重编，没有构建 RUNPATH 或 `/usr/local` 默认路径，并在清除临时环境修正后通过全部真实会话检查。交付包及 SHA256 清单均为修正后的版本。

`pacman -Qkk` 对 libwireplumber 无差异；libpipewire 仅提示 `/usr/share/man` 缺失，这是当前既有 `NoExtract = usr/share/man/*` 策略，已安装修补模块内容校验一致。

## 范围

本轮自动播放使用静音样本验证应用路由，之前用户已确认听到声音；没有把静音回归当成新的听感确认。未实际重启手机，未验证 USB 或远程摄像头视频捕获。当前桌面是 Niri；KDE／GNOME／Gamescope 已验证规则安装和包元数据，没有启动各桌面作端到端测试。

底层补丁作用于已经复现的设备导出失败路径，Anland 补丁作用于已确认的 Qualcomm 节点。Android 音量、蓝牙／扬声器输出选择以及 consumer 断连等其他原因仍属于独立问题。


## Anland 集成

完整补丁包含 19 个文件。新增共享 WirePlumber 配置、包依赖 helper 和 11 项测试；修改 KDE、GNOME、Niri、Gamescope 的安装及包文件清单，并补充双语指南。每个 producer 使用独立配置文件名，避免多个桌面包共同拥有同一路径。Arch / SteamOS 要求 WirePlumber >=0.5.18；Debian / Ubuntu / Fedora 允许 <0.5.16 或 >=0.5.18。

## 底层修复分别提交

PipeWire 的 proxy-device.c 检查 spa_device_add_listener 返回值；负错误时销毁 proxy，保存 errno 后返回 NULL。WirePlumber 的 device.c 保存 export 返回值和 errno，仅成功才绑定 proxy；失败时解锁并让 transition 返回操作错误。两个源码补丁需要分别提交 PipeWire / WirePlumber 上游；Anland PR 目标是 legacy。

本报告引用的 validation/ 及 upstream-root-fixes/ 文件位于 anland-audio-PR-materials.zip 内。报告描述本次本机验证，未来云运行结果以对应 Actions 日志为准。
