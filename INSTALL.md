# 安装、验证与回退

## 选择安装方式

| 你的环境 | 方式 |
| --- | --- |
| 已有 Anland legacy 桌面，想先避免已确认的高通节点故障 | 安装精准过滤配置 |
| Arch Linux ARM aarch64，原版 libpipewire 为 1:1.6.9-1、libwireplumber 为 0.5.18-1 | 配置 + 云编译成对根修包 |
| Debian / Ubuntu / Fedora / 其他版本 | 配置修复；底层源码用本发行版构建方式移植 |
| Anland main 6.x | 音频链路不同，先核对版本；本补丁面向 legacy |

当前任务中已经修复的原机器无需再安装一次。

## 一、下载仓库

```sh
git clone https://github.com/mzbgq29-ui/anland-audio-fix.git
cd anland-audio-fix
```

## 二、安装精准过滤配置

先检查 WirePlumber：

```sh
wireplumber --version
```

使用 WirePlumber 0.5 配置语法。未修补的 **0.5.16 和 0.5.17 必须先升级**，或确认发行版已回移 [65519a1](https://github.com/PipeWire/wireplumber/commit/65519a1ff7cecebc0622fc4a2badec830ee67d7d)。建议 0.5.18 或更新版本。0.5.8、0.5.12、0.5.15 的同步 hook 没有这一特定回归；WirePlumber 0.4 不支持此配置格式。

在 Linux 环境内执行：

```sh
sudo install -Dm644 50-anland-android-camera.conf \
  /etc/wireplumber/wireplumber.conf.d/50-anland-android-camera.conf
systemctl --user restart wireplumber.service
wpctl status
```

`systemctl --user` 必须以启动桌面的普通用户执行。使用其他服务管理器的环境，请按其方式重启 WirePlumber。

检查 `/etc/wireplumber/wireplumber.conf.d/` 和 `~/.config/wireplumber/wireplumber.conf.d/` 中自己曾添加的旧配置。如果存在 `hardware.video-capture = disabled`，移除这一设置或将那份旧片段移出配置目录，保留其他无关配置。若 producer 包已安装本规则，不必重复安装同一规则。

规则仅匹配 Qualcomm `cam-req-mgr`、`cam-sync`、`vidc` 的 sysfs 身份，不依赖 `/dev/videoN` 编号，也不关闭整个视频捕获功能。

## 三、安装成对根修包（限定基线）

检查架构和版本：

```sh
uname -m
pacman -Q libpipewire libwireplumber
```

应为 aarch64、`libpipewire 1:1.6.9-1`、`libwireplumber 0.5.18-1`。本仓库修补版 `1.1` 对应同一基线。其他版本不要强制降级或用 `--nodeps` 安装，应该更新构建基线。

可从 [Release v0.1.0](https://github.com/mzbgq29-ui/anland-audio-fix/releases/tag/v0.1.0) 下载本机已经验证的安装包 ZIP，解压后使用。也可按照 [云编译教程](CLOUD_BUILD.md) 下载成功运行的 artifact ZIP，先解压 ZIP，再解压内部的 tar.gz：

```sh
tar -xf anland-audio-archlinuxarm-aarch64.tar.gz
```

在解压后的包目录检查：

```sh
sha256sum -c SHA256SUMS
```

结果应全部为 OK，自行云编译时，运行本身也必须绿色成功，并包含 `verification.json` 和成功的 `regression-results/report.json`。失败运行上传的诊断 artifact 不用于安装。

两个修补包是你自己云编译的本地包，未带发行版官方签名；官方回退包保留签名。若本机要求本地包签名，可为本次安装生成独立配置，不修改全局设置：

```sh
python3 - <<'PY'
from pathlib import Path
import re
text=Path('/etc/pacman.conf').read_text()
text,count=re.subn(r'(?m)^\s*#?\s*LocalFileSigLevel\s*=.*$',
                  'LocalFileSigLevel = Optional',text)
if not count:
    text=text.replace('[options]\n','[options]\nLocalFileSigLevel = Optional\n',1)
Path('pacman-local-build.conf').write_text(text)
PY
sudo pacman --config "$PWD/pacman-local-build.conf" -U \
  'patched/libpipewire-1:1.6.9-1.1-aarch64.pkg.tar.xz' \
  'patched/libwireplumber-0.5.18-1.1-aarch64.pkg.tar.xz'
systemctl --user restart wireplumber.service
```

安装必须同时包含两包：只修 PipeWire 会触及 WirePlumber 的 NULL proxy 断言，只修 WirePlumber 则仍可能等待。

## 四、验证播放

```sh
systemctl --user is-active pipewire.service wireplumber.service
wpctl status
pactl info
```

确认存在 `anland-speaker`，应用使用它；PulseAudio 兼容应用的默认 sink 也应是 `anland-speaker`。用普通播放应用播放实际音频，检查 Android 媒体音量与 Anland 播放设置。可以重启 WirePlumber 后再次播放，确认不会再次卡住。不要以能看到设备名称替代实际播放检查。

使用摄像头时单独测试 USB／Anland 摄像头捕获：摄像头节点仍可见，不等于视频捕获已验证。

## 五、回退

保留过滤配置，联合安装 artifact 内带官方签名的原版库：

```sh
sudo pacman -U 'original/libpipewire-1:1.6.9-1-aarch64.pkg.tar.xz' \
  'original/libwireplumber-0.5.18-1-aarch64.pkg.tar.xz'
systemctl --user restart wireplumber.service
```

默认 pacman 配置验证官方签名。精准规则继续防止已知节点触发旧库错误。以后发行版升级会替换本地库，但 `/etc` 中的规则会保留；底层修复由发行版发布后可恢复使用官方库。

## 六、把 Anland 改动放入自己的 fork

在 Anland fork 的 legacy 基线新分支中：

```sh
git apply --check /path/to/anland-audio-fix.patch
git apply /path/to/anland-audio-fix.patch
python3 -m unittest discover -s libdisplay_producer/wireplumber/tests -v
```

基线提交为 `a271f010b0f2ed413e193e779e38daa77070c974`。测试需要 `spa-json-dump`、Bash、Python 3，以及 `dpkg` 或 `vercmp`。按 producer 原有脚本重新打包桌面后，新包会自动携带规则及 WirePlumber 版本保护。
