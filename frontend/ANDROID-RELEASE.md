# 见闻 Android 发行

沿用 uni-app / HBuilderX 官方 App 云打包，不用 H5 构建结果冒充 APK。

- 应用名：见闻；包名：`com.jianwen.app`；版本：`1.0.0` / `100`。
- 本机 `.env.production` 已设 `VITE_API_BASE_URL=http://8.147.110.194`，该文件被 Git 忽略。其他机器打包前创建同名文件并填写这个公开 API 地址。
- `AndroidManifest.xml` 与 `nativeResources/android/res/xml/jianwen_network_security_config.xml` 将明文网络限定到当前服务器 IP，其余地址只允许 HTTPS。以后迁移 HTTPS 时移除该例外。
- manifest 移除了模板中的读取电话状态、账号、系统设置、日志、挂载与修改网络等权限；保留网络、头像拍照、旧安卓相册和播放唤醒需求。最终仍需检查云打包 APK 合并后的实际权限。

## 当前打包状态

2026-11-01 实际调用 HBuilderX 5.34 官方 CLI：

1. `pack --config <本机私有配置路径>` 返回 `user not login`。
2. `publish app --type appResource --project <frontend绝对路径>` 返回“项目的AppID不能为空”。

上述登录与 AppID 问题已解决，当前应用标识为 `__UNI__8D7394F`。官方打包插件已安装；排除权限改为 HBuilderX 要求的 XML 格式后通过格式校验。重新生成 App 资源时，DCloud 明确拦截：当前账号及应用所有者尚未绑定手机号，需在 https://dev.dcloud.net.cn/pages/user/info 由用户完成绑定。尚无成功提交的云打包任务，也无 APK。

用户已同意本轮 Google SDK / Google APIs ARM64 镜像许可。build-tools 36、Android 35 Google APIs ARM64 镜像及模拟器已安装，AVD `jianwen-api35` 已冷启动完成，adb 识别 `emulator-5554`。安装和功能验收仍需等待实际 APK；11 项前端单元测试通过不代表 Android 验收通过。

## 签名与后续打包

本机已生成专用 RSA 3072 位 release keystore，别名 `jianwen-release`，有效期至 2054 年。私钥、密码和云打包配置位于项目外的私有目录，权限为目录 `700` / 文件 `600`，另有同机私有备份；未提交、未上传到网页目录。需由用户另行作离机加密备份。

当前证书 SHA-256 指纹：`12:02:65:35:A7:49:8D:67:9D:90:3D:F9:CC:57:E0:2F:6A:E2:95:D5:1F:0B:93:4C:DF:29:C4:38:A4:7C:0D:BA`。

用户登录并取得 AppID 后，使用本机私有 `cloud-pack.json` 配置运行 HBuilderX `cli pack --config`。配置固定为正式自有证书、Android、无开屏/悬浮/激励广告，不包含 iOS 或渠道分包。

## 产物验收

- 使用 Android build-tools 检查 APK 包名、版本、权限、网络配置与签名；计算 SHA-256。
- 全新安装和同签名覆盖安装；检查今日/发现图片、文章/经典、三期视频、账号恢复、周报相册保存、头像选图和前后台恢复。
- 不发送测试短信、不改真实账号数据。没有真机时明确记录模拟器范围，不宣称真机通过。
- 验证后的 APK 才交由部署方发布 `/downloads/jianwen-1.0.0.apk`，同时公布版本、大小和 SHA-256。
