# GitHub Actions 云编译教程

## 一、直接在本仓库编译

1. 打开仓库的 **Actions**。
2. 选择 **ARM64 audio root fixes**。
3. 点击 **Run workflow**，选择 `main`，再确认运行。
4. 等待运行显示绿色成功。
5. 打开该运行详情，在 **Artifacts** 下载 `anland-audio-archlinuxarm-aarch64`。
6. 解压 artifact ZIP 后，再解压其中的 `anland-audio-archlinuxarm-aarch64.tar.gz`，按 [安装教程](INSTALL.md) 校验并安装。

只有有写入权限的账号能手动运行本仓库 workflow。其他用户可先 Fork；Fork 后打开 Actions 并启用自己仓库的流程，再按同样步骤运行。下载 artifact 通常需要登录 GitHub。产物保留 30 天，需要时重新运行。

## 二、编译内容

工作流使用 GitHub 原生 `ubuntu-24.04-arm` runner。Ubuntu 仅提供 runner 与 Docker；库和 pacman 包都在通过 HTTPS 下载的**官方 Arch Linux ARM aarch64 rootfs** 内编译，因此不会把 Ubuntu 构建的库误当成 Arch 包。

流程依次：

1. 下载官方 rootfs，记录 SHA256 和最终环境包版本。
2. 在隔离容器中安装构建工具并初始化官方 keyring。容器不支持 pacman 的 Landlock 文件系统下载沙箱，命令使用 `--disable-sandbox-filesystem`，保留其余下载沙箱和全部官方签名验证。
3. 确认库与 daemon 仍对应本次固定基线。
4. 下载 PipeWire 1.6.9 / WirePlumber 0.5.18 源码，验证固定 SHA256，严格应用补丁。
5. 使用 `/usr`、`/etc`、`/var` 路径编译目标库，去掉构建 RUNPATH。
6. 下载固定版本官方原包，验证固定 SHA256 和官方签名。
7. 使用 makepkg 保留原包完整 payload，仅替换目标 ELF，保留 ABI 和原精确版本兼容关系。
8. 比较所有文件、链接和元数据，运行隔离故障注入与 Anland 11 项回归。
9. 上传两份修补包、官方回退包、配置及验证证据。

不需要任何账户密码、GitHub Token 或额外 Secrets。workflow 的默认权限仅为 `contents: read`，不会自动发布 Release、提交上游 PR 或推送构建产物到源码分支。

GitHub artifact 不允许文件路径包含冒号，而 Arch 的 epoch 版本包名含 `1:`。流程将精确包名和校验材料封装在 tar.gz 内上传，避免重命名包及破坏校验清单。

## 三、产物目录

| 文件／目录 | 内容 |
| --- | --- |
| `patched/` | 两份 aarch64 根修包，pkgrel 1.1 |
| `original/` | 对应官方原版包及 `.sig`，用于回退 |
| `SHA256SUMS` | 原版与修补包校验 |
| `verification.json` | 逐文件 payload、元数据、签名及安装计划检查 |
| `regression-results/` | 故障注入结果与 Anland 回归日志 |
| `BUILD-ENVIRONMENT.txt` | 容器内最终包版本 |
| `ROOTFS-SHA256SUMS` | 本次官方 rootfs 的实际哈希记录 |
| `50-anland-android-camera.conf` | 精准过滤规则 |

rootfs 使用官方 latest，构建环境随官方更新；源代码与官方原包哈希固定。它提供可追溯构建，不声称不同日期的产物完全逐字节相同。当前完整桌面安装验证在本地完成；云端只做无硬件隔离测试，不能验证 Android 实际听感或摄像头捕获。

## 四、常见失败

- **runner 不可用／排队：**本工作流需要支持公开仓库的原生 ARM64 runner。组织策略禁用时需调整策略或提供原生 aarch64 self-hosted runner。
- **基线版本检查失败：**官方仓库已经升级。流程故意停止；不要去掉检查后拿旧版本库拼进新包。需要更新源码标签、补丁上下文、原包来源与哈希、SONAME／精确依赖，以及回归测试。
- **旧官方包 404：**当前镜像不再保留该版本，使用官方 archive 或自己保留、官方签名有效且哈希一致的原版包。
- **签名／SHA256 失败：**检查下载来源与版本，不能通过关闭验证继续。
- **失败运行出现 artifact：**`if: always()` 用于保留诊断。只有绿色运行且包含所有验证结果的包可安装。
- **下载慢：**rootfs 约 830 MB，首次下载和更新耗时较长；原生 ARM 编译避免 QEMU 模拟。当前超时设为 60 分钟。

## 五、在自己的 ARM64 Linux 主机复现

安装 Docker、curl、Git 后，在仓库根目录执行：

```sh
bash cloud-build.sh
```

Docker 需要正常运行和当前用户的调用权限。产物生成在 `artifacts/`，临时环境在 `.cloud-work/`。这是容器构建，不会改主机的 PipeWire/WirePlumber 服务或系统包。
