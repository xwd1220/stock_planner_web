# 股票交易计划工具

一个面向个人投资计划管理的轻量 Web 工具，帮助用户为股票或 ETF 生成分批买入、分批卖出计划，并保存历史方案以便复盘和对比。

当前版本已经支持：

- 标的配置
- 买入计划生成
- 卖出计划生成
- 计划保存
- 历史查看与回填

项目使用 Python 标准库实现本地 Web 服务与 SQLite 存储，依赖简单，适合先做内部原型或个人使用。

## 功能概览

### 1. 标的配置

支持维护标的基础信息：

- 标的代码
- 标的名称
- 标的类型
- 币种
- 备注

### 2. 买入计划生成器

根据以下参数生成分批买入计划：

- 初始买入价格
- 计划资金
- 买入频率
- 买入次数
- 首单数量
- 买单倍数

买入规则：

- 第 1 笔数量 = 首单数量
- 后续每笔价格按设定频率逐级下降
- 后续每笔数量 = 上一节点数量 × 当前节点倍数
- 自动计算每笔消耗资金、累计投入、累计数量、持仓成本

### 3. 卖出计划生成器

根据以下参数生成分批卖出计划：

- 持仓成本
- 总持仓数量
- 计划卖出数量
- 目标回收资金
- 初始卖出价格
- 初始执行价格
- 卖出频率
- 卖出次数
- 卖单倍数

卖出规则：

- 卖出价格用于计算回收资金
- 执行价格用于计算计划资金
- 两条价格序列按设定频率逐级上升
- 卖出数量按倍数权重分配
- 最后一笔自动吸收舍入误差

### 4. 历史计划管理

支持：

- 保存买入计划
- 保存卖出计划
- 查看历史列表
- 点击历史记录回填到当前页面

## 技术栈

- Python 3.10+
- 标准库 WSGI 服务：`wsgiref`
- SQLite：计划与历史存储
- 原生 HTML / CSS / JavaScript
- `pytest`：测试

说明：

- 应用运行本身不依赖第三方 Web 框架
- 测试需要额外安装 `pytest`

## 快速开始

### 1. 进入项目目录

```powershell
cd "D:\codex project\stock_planner_project"
```

### 2. 启动本地服务

从工作区根目录启动：

```powershell
python -m stock_planner_project.stock_planner.cli serve --host 127.0.0.1 --port 8008
```

然后在浏览器打开：

`http://127.0.0.1:8008`

### 3. 运行演示数据

```powershell
python -m stock_planner_project.stock_planner.cli demo
```

这个命令会输出一组示例买入/卖出计划结果，便于快速验证计算逻辑是否正常。

## 测试

如果本地尚未安装 `pytest`，先安装：

```powershell
pip install pytest
```

运行测试：

```powershell
python -m pytest stock_planner_project\tests\test_stock_planner_buy_plan.py stock_planner_project\tests\test_stock_planner_sell_plan.py stock_planner_project\tests\test_stock_planner_storage.py stock_planner_project\tests\test_stock_planner_web.py --basetemp .tmp\pytest-temp -p no:cacheprovider
```

当前已覆盖：

- 买入计划计算
- 卖出计划计算
- 存储读写
- Web 接口
- 历史计划保存与加载

## 项目结构

```text
stock_planner_project/
├─ README.md
├─ stock-planner-v1-plan.md
├─ __init__.py
├─ stock_planner/
│  ├─ __init__.py
│  ├─ cli.py
│  ├─ models.py
│  ├─ storage.py
│  ├─ web.py
│  ├─ services/
│  │  ├─ __init__.py
│  │  ├─ buy_plan.py
│  │  ├─ sell_plan.py
│  │  └─ rounding.py
│  └─ static/
│     └─ index.html
└─ tests/
   ├─ test_stock_planner_buy_plan.py
   ├─ test_stock_planner_sell_plan.py
   ├─ test_stock_planner_storage.py
   └─ test_stock_planner_web.py
```

## 主要接口

当前页面使用的主要接口如下：

- `GET /`
- `GET /health`
- `GET /api/symbols`
- `POST /api/symbols`
- `POST /api/buy-plans/calculate`
- `POST /api/sell-plans/calculate`
- `GET /api/buy-plans`
- `GET /api/sell-plans`
- `POST /api/buy-plans`
- `POST /api/sell-plans`
- `GET /api/buy-plans/{id}`
- `GET /api/sell-plans/{id}`

## 当前限制

- 暂未接入实时行情
- 暂未支持 VIX 监控与回撤提醒
- 暂未支持导出 Excel / CSV
- 暂未支持删除历史计划
- 页面当前为单用户本地使用场景设计

## 后续规划

- 增加历史删除与筛选
- 增加 CSV / Excel 导出
- 增加实时行情接入
- 增加条件触发提醒
- 根据需要升级为前后端分离架构

## 说明文档

更完整的业务与实现方案请见：

[stock-planner-v1-plan.md](./stock-planner-v1-plan.md)
