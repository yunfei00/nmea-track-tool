# NMEA Slimmer (PySide6)

用于将原始 NMEA 文本精简为更适合 GSS7000 轨迹回放与 GNSS 测试分析的文件。

## GSS7000 推荐规则

默认仅保留：`GGA`、`RMC`、`GSA`、`GSV`。

默认删除：`VTG`、`GNS`、`DTM`、未知语句、非 NMEA 行。

## 界面说明

主窗口提供：
- 输入文件选择
- 输出文件选择（默认 `<原文件名>_slim.nmea`）
- 精简模式勾选项（保留/删除规则）
- talker 统一为 `GP`
- GSV 降频秒数（0=不降频）
- 开始精简 / 预览统计
- 日志输出框、进度条、结果统计区域

## 使用步骤

1. 安装依赖：`pip install -r requirements.txt`
2. 启动：`python -m src.nmea_slimmer.app`
3. 选择输入文件（支持 `.nmea/.txt/.log/.csv`）
4. 设置输出路径与规则
5. 点击“开始精简”

## 精简规则说明

- 识别 talker + sentence type（如 `GNGGA/GPGGA/BDGGA -> GGA`）。
- 可选将 talker 统一转换为 `GP`，并重算 checksum。
- 可选 GSV 降频；当启用时按时间桶控制，并尽量保留同一时刻完整组。
- 原始文件不会被覆盖（默认另存）。


## CI/CD

- Push 到 `main` / `master` / `dev` 会自动执行测试与构建，并上传 Windows 可执行文件 artifact。
- 推送 `v*` 标签（如 `v1.0.0`）会自动执行测试与构建、打包 ZIP、创建 GitHub Release，并仅上传包含可执行文件的 `.zip` 资产。
