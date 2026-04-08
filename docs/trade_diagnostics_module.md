# 历史交易诊断模块 V1

## 页面原型

### 1. 工作区切换
- `AI 选股终端`
- `历史交易诊断`

### 2. 历史交易诊断页面
- 左栏 `导入中心`
  - 导入模板选择
  - CSV / XLSX 文件上传
  - 导入指引
  - 最近批次
- 中栏 `交易风格体检`
  - 交易画像
  - 核心指标
  - 盈利单 vs 亏损单
- 右栏 `诊断结论`
  - 错误模式识别
  - 有效模式总结
  - 策略优化建议
  - 标准字段说明

## API 设计

### `GET /api/trade-diagnostics/profiles`
- 返回支持的券商导入模板
- 返回标准字段说明

### `POST /api/trade-diagnostics/import`
- 表单字段
  - `profile_id`
  - `file`
- 当前支持
  - `csv`
  - `xlsx`

### `GET /api/trade-diagnostics/summary`
- 返回最近一次导入批次的交易风格诊断
- 若没有真实数据，则返回 demo 诊断结果

### `GET /api/trade-diagnostics/schema`
- 返回数据库表结构蓝图
- 方便后续接入更多模板和批处理任务

## 数据库表结构

### `import_batches`
- `batch_id TEXT PRIMARY KEY`
- `imported_at TEXT NOT NULL`
- `broker TEXT NOT NULL`
- `source_type TEXT NOT NULL`
- `filename TEXT NOT NULL`
- `detected_format TEXT NOT NULL`
- `row_count INTEGER NOT NULL`
- `imported_count INTEGER NOT NULL`
- `ignored_count INTEGER NOT NULL`
- `symbol_count INTEGER NOT NULL`
- `start_date TEXT`
- `end_date TEXT`
- `notes TEXT`

### `trades`
- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `batch_id TEXT NOT NULL`
- `trade_date TEXT NOT NULL`
- `trade_time TEXT`
- `symbol TEXT NOT NULL`
- `stock_name TEXT`
- `market TEXT`
- `side TEXT NOT NULL`
- `quantity INTEGER NOT NULL`
- `price REAL NOT NULL`
- `amount REAL NOT NULL`
- `commission REAL NOT NULL DEFAULT 0`
- `stamp_tax REAL NOT NULL DEFAULT 0`
- `transfer_fee REAL NOT NULL DEFAULT 0`
- `other_fee REAL NOT NULL DEFAULT 0`
- `net_amount REAL NOT NULL`
- `account_masked TEXT`
- `broker TEXT NOT NULL`
- `source_type TEXT NOT NULL`
- `raw_row_id INTEGER`

## 当前实现边界
- 已支持 `CSV / XLSX` 的 MVP 导入
- 已支持通用字段映射和常见中文列名别名
- 已支持基于 FIFO 的闭环交易配对
- 已支持风格画像、盈亏对比、错误模式和建议生成
- 暂未实现 PDF / OCR 解析
- 暂未实现多券商逐字段人工映射确认页
