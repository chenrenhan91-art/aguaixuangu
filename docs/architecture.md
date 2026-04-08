# 架构说明

当前项目骨架遵循“HTML 可直出 + 选股核心功能优先”的分层思路，并增加了历史交易诊断工作区：

- 数据采集层：`data_pipeline/adapters`
- 数据清洗与校验层：`data_pipeline/validators`
- 策略服务层：`backend/app/services`
- API 暴露层：`backend/app/api`
- 展示层：`backend/app/static`
- 交易导入与诊断存储：`data/processed/trade_diagnostics.sqlite3`

## 数据流

1. `daily_refresh` 任务采集原始数据并落盘到 `data/raw`
2. `generate_daily_candidates` 任务完成行业筛选、事件聚合、候选池排序和离线 HTML 导出
3. 后端服务读取最新快照，并通过 REST API 提供市场情绪、行业、候选池和个股解释
4. HTML 页面通过 REST API 渲染选股终端
5. 历史交易诊断模块通过上传 CSV / XLSX 文件，将标准化成交记录写入 SQLite，并基于 FIFO 闭环交易生成交易画像

## 后端设计

- `core`: 配置和应用级依赖
- `models`: 领域模型
- `schemas`: API 输入输出结构
- `services`: 业务服务
- `api/routes`: 路由层

## 展示层设计

- 默认展示入口为 `backend/app/static/index.html`
- `app.js` 负责调用 API 并渲染候选池、个股详情和历史交易诊断页面
- `styles.css` 提供单页仪表盘样式

## 替换真实数据时的建议顺序

1. 先替换数据管道适配器
2. 再将服务层改成读取真实存储
3. 最后替换前端中的示例文案和展示字段
