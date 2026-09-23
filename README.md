# 海上无人补给 / 作战平台资料库

这是一个面向资料检索、装备对照与原文核验的本地数字图鉴。项目采用 **Python Flask + SQLite + Jinja + 自有 CSS + 少量原生 JavaScript**，把两份工作簿中的海上无人平台整理成可搜索、可筛选、可进入详情、可横向比较的网站。

当前数据库包含 **22 型平台（第一批 12 型、第二批 10 型）**，覆盖 **6 个国家 / 地区、30 条活动记录和 67 个原文入口**，其中包括 6 型中国平台。网站保留原表的 L / L/W / W 标签、E2–E5 证据等级、未达 E2 状态、八项公开性能、活动记录、操控与人员参与说明，以及可直接打开的原文入口。

## 1. 当前功能

### 平台目录

- 卡片网格与紧凑列表两种视图；切换视图时保留当前查询条件。
- 按名称、国家 / 地区、能力标签、资料批次、证据等级组合筛选；可单独查看“未评级 / 未达 E2”记录。
- 关键词同时检索平台名称、国家 / 地区、平台类型、载荷描述和活动记录。
- 卡片展示主图、标签、国家、重点性能和活动摘要；缺失性能以 `—` 表示，不按 0 处理。
- 手机端使用抽屉式筛选，桌面端使用固定侧栏。

### 平台档案

- 多图画廊、图片说明与图片原始来源。
- 基本信息、任务载荷、八项公开性能、能力标签。
- 演习 / 部署 / 实战活动时间线。
- 操控方式与人员参与说明。
- 性能、活动、操控三组原文链接与核验备注。

### 装备对比

- 在目录卡片、列表行或档案页点击“加入对比”。
- 一次选择 **2–4 型**平台；选择保存在浏览器 `localStorage` 中，换页后仍会保留。
- 对比页并列展示基础信息、公开性能和性能来源，保留原始单位及“约 / 最高 / ≥ / >”等限定条件。
- 对比地址使用 `ids` 参数，例如：`http://127.0.0.1:5000/compare?ids=1,2,3`。

本版定位为本机只读资料站：数据维护通过 Excel 导入、SQLite 迁移和 SQL 完成；账号体系、在线编辑、自动采集与复杂前端框架留作后续迭代。

## 2. 技术结构

```text
website_catalog/
├─ app.py                         Flask 入口、参数化查询、页面路由
├─ import_data.py                 Excel → SQLite 的可重复导入脚本
├─ migrate.py                     前向、增量、可重复执行的迁移脚本
├─ manage_images.py               图片记录的校验与维护命令行工具
├─ schema.sql                     新数据库的完整结构
├─ requirements.txt               Python 依赖
├─ data/
│  ├─ source.xlsx                 原始工作簿副本
│  ├─ source_china.xlsx           中国平台工作簿副本
│  └─ platforms.sqlite3           默认 SQLite 数据库
├─ migrations/
│  └─ 001_add_platform_images.sql 图片表迁移
├─ templates/                     Jinja 页面及复用片段
├─ static/
│  ├─ css/app.css                 响应式界面样式
│  ├─ js/app.js                   导航、移动筛选、图库交互
│  ├─ js/compare.js               2–4 型平台选择与对比状态
│  └─ img/
│     ├─ placeholder-platform.svg 明确标注的缺图占位图
│     └─ platforms/               后续添加的本地平台图片目录
├─ screenshots/                   桌面首页、档案、对比及手机验收截图
├─ tests/test_site.py             导入、筛选、档案、图片、对比与迁移测试
├─ THIRD_PARTY_NOTICES.md         第三方组件借鉴说明
└─ LICENSES/Classimax-MIT.txt     Classimax 的 MIT 许可证副本
```

## 3. Windows 快速启动

以下命令均在项目根目录执行。使用虚拟环境中的 Python 完整路径，可避开 PowerShell 激活脚本权限设置。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe migrate.py
.\.venv\Scripts\python.exe import_data.py
.\.venv\Scripts\python.exe app.py
```

浏览器打开：<http://127.0.0.1:5000/>  
终端按 `Ctrl+C` 结束本地服务。

仓库已包含默认数据库，因此快速启动中先运行迁移、再重新导入。`migrate.py` 具有幂等性；数据库已经是最新结构时会显示“数据库已经是最新结构”。

### macOS / Linux

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python migrate.py
./.venv/bin/python import_data.py
./.venv/bin/python app.py
```

## 4. 数据库初始化、迁移与导入

### 4.1 全新数据库

`import_data.py` 会读取 `schema.sql`，自动建立完整表结构。用一个新文件测试时：

```powershell
.\.venv\Scripts\python.exe import_data.py --db data\platforms-dev.sqlite3
$env:PLATFORM_DB = (Resolve-Path data\platforms-dev.sqlite3)
.\.venv\Scripts\python.exe app.py
```

关闭该终端后，`PLATFORM_DB` 环境变量随会话结束。回到默认数据库时也可执行：

```powershell
Remove-Item Env:PLATFORM_DB -ErrorAction SilentlyContinue
```

### 4.2 从旧版数据库升级

先保存一份数据库副本，再执行迁移：

```powershell
Copy-Item data\platforms.sqlite3 data\platforms.before-image-migration.sqlite3
.\.venv\Scripts\python.exe migrate.py
```

指定另一个数据库：

```powershell
.\.venv\Scripts\python.exe migrate.py --db "D:\资料库\platforms.sqlite3"
```

迁移记录保存在 `schema_migrations` 表中。每个 `migrations/*.sql` 文件只执行一次；已存在的 `platforms`、`activities` 和 `source_links` 数据原样保留。

### 4.3 原子导入项目内两份工作簿

```powershell
.\.venv\Scripts\python.exe import_data.py
```

省略 `--xlsx` 时，脚本会在同一事务中导入 `data/source.xlsx` 与 `data/source_china.xlsx`，默认输出为 `data/platforms.sqlite3`。任一工作簿校验失败时整次事务都会回滚，不会只更新一半数据。导入脚本读取普通 Excel 超链接和 `HYPERLINK(...)` 公式中的原文地址，但不会执行公式或访问网页。

两份内置工作簿使用稳定来源键：

| 工作簿 | 来源键 | 当前记录 |
|---|---|---:|
| `data/source.xlsx` | `global` | 16 型 |
| `data/source_china.xlsx` | `china` | 6 型 |

导入脚本会校验：

- 每份工作簿恰好包含两个工作表；
- 每份工作簿的两个工作表都至少包含一条平台记录；
- 标签属于 `L`、`L/W`、`W`；
- 来源链接使用完整的 HTTP 或 HTTPS 地址。

### 4.4 单独导入一份工作簿

项目内文件可使用自动识别出的稳定来源键：

```powershell
.\.venv\Scripts\python.exe import_data.py --xlsx data\source_china.xlsx
```

从项目外导入时必须同时提供稳定且唯一的 `--source-key`。例如单独更新中国平台：

```powershell
.\.venv\Scripts\python.exe import_data.py `
  --xlsx "E:\资料库\中国海上无人补给作战平台数据库_2026-09-23.xlsx" `
  --source-key china `
  --db data\platforms.sqlite3
```

更新原有全球平台工作簿时使用 `--source-key global`。后续增加第三份工作簿时，应为它分配新的 ASCII 来源键，例如 `regional_2026`；来源键可使用字母、数字、点、下划线和连字符。

### 4.5 重复导入为何会保留图片

平台按名称执行 UPSERT，原平台 ID 得以复用；每份工作簿由稳定来源键隔离，中国工作表的内部坐标形如 `china::工作表名`，不会与全球工作簿的同名工作表和行号冲突。导入前会在同一事务中临时释放当前来源的工作表行号坐标，因此工作表内重排或插入行也不会改变既有平台 ID。脚本仅刷新由工作簿维护的 `activities` 与 `source_links` 子记录，人工维护的 `platform_images` 不参与刷新，所以第二次、第三次导入后仍会保留。

平台名称承担稳定身份。如果工作簿删除或重命名已有平台，导入器会停止并回滚本次事务，提示先显式处理映射，避免图片误挂到另一型平台。

导入前做数据库副本依然是良好习惯，尤其适合工作簿发生平台重命名或字段结构调整时。

## 5. 页面地址与筛选参数

| 页面 | 地址 | 说明 |
|---|---|---|
| 平台目录 | `/` | 默认网格视图 |
| 列表视图 | `/?view=list` | 使用相同筛选器的紧凑列表 |
| 平台档案 | `/platform/1` | `1` 为平台 ID |
| 装备对比 | `/compare?ids=1,2` | ID 以英文逗号分隔，最多 4 个 |
| 项目说明 | `/about` | 数据口径、标签与开源说明 |

目录可组合使用这些查询参数：

| 参数 | 示例 | 含义 |
|---|---|---|
| `q` | `?q=演习` | 名称、国家、类型、载荷或活动关键词 |
| `country` | `?country=美国` | 国家 / 地区精确筛选 |
| `label` | `?label=L%2FW` | `L`、`L/W` 或 `W` |
| `batch` | `?batch=1` | 第一批或第二批 |
| `evidence` | `?evidence=E3` | E2–E5 证据等级；使用 `unrated` 查看未评级 / 未达 E2 记录 |
| `view` | `?view=grid` | `grid` 或 `list` |

所有数据库筛选均使用参数化 SQL。用户输入中的 `%` 和 `_` 会按普通字符处理。

## 6. SQLite 数据模型

| 表 | 用途 | 关键关系 |
|---|---|---|
| `platforms` | 一型平台的基础信息、标签、批次、八项性能、操控与证据 | 主表 |
| `activities` | 从活动描述拆分出的时间线记录 | `platform_id → platforms.id` |
| `source_links` | 性能、活动、操控三类原文入口 | `platform_id → platforms.id` |
| `platform_images` | 本地或网络图片、说明、来源、类型、顺序、主图状态 | `platform_id → platforms.id` |
| `schema_migrations` | 已执行的增量迁移 | 由 `migrate.py` 维护 |

`activities`、`source_links`、`platform_images` 都使用外键并随所属平台级联删除。

### `platform_images` 字段

| 字段 | 含义 |
|---|---|
| `image_url` | 网络图片的完整 HTTP / HTTPS 地址 |
| `local_path` | 相对于 `static/` 的本地路径，例如 `img/platforms/seagull/side.jpg` |
| `caption` | 图注，建议包含场景、视角或日期 |
| `source_url` | 图片出处网页的完整 HTTP / HTTPS 地址 |
| `source_name` | 出处名称，例如“厂商官网”或“演习新闻稿” |
| `image_type` | `official`、`exercise`、`combat`、`manufacturer`、`control`、`loading`、`other` 之一 |
| `is_primary` | `1` 表示主图，`0` 表示普通图；每个平台最多一张主图 |
| `sort_order` | 普通图排序，数值越小越靠前 |

图片读取顺序为：主图优先，其余按 `sort_order`、`id` 排序。卡片和对比页使用第一张图片，档案页显示全部图片缩略图。

## 7. 添加第 1、2、3 张图片

优先使用 `manage_images.py`。它会检查平台 / 图片 ID、图片类型、HTTP(S) URL、本地路径范围和单主图约束，比直接写 SQL 更适合日常维护。

先查看平台 ID（也可用 DB Browser 查询 `platforms` 表），再查看现有图片：

```powershell
.\.venv\Scripts\python.exe manage_images.py list --platform-id 1
```

添加第 1 张本地图片并设为主图：

```powershell
.\.venv\Scripts\python.exe manage_images.py add `
  --platform-id 1 `
  --local-path img/platforms/alpv/official-01.jpg `
  --caption "官方视图" `
  --image-type official `
  --source-name "厂商官网" `
  --source-url https://www.example.org/platform-page `
  --primary
```

添加第 2、3 张图库图片（可混合网络图与本地图）：

```powershell
.\.venv\Scripts\python.exe manage_images.py add --platform-id 1 `
  --image-url https://images.example.org/alpv/exercise.jpg `
  --caption "演习画面" --image-type exercise --sort-order 20

.\.venv\Scripts\python.exe manage_images.py add --platform-id 1 `
  --local-path img/platforms/alpv/loading.jpg `
  --caption "任务载荷装载" --image-type loading --sort-order 30
```

将已有图片设为主图，或删除图片记录：

```powershell
.\.venv\Scripts\python.exe manage_images.py set-primary 25
.\.venv\Scripts\python.exe manage_images.py delete 25
```

操作其他数据库时，将全局 `--db` 放在子命令前：

```powershell
.\.venv\Scripts\python.exe manage_images.py --db data\platforms-dev.sqlite3 list
```

下面保留等价 SQL，适合批量维护或审计数据库变更。可在 [DB Browser for SQLite](https://sqlitebrowser.org/) 的“执行 SQL”页签中运行；本机安装了 `sqlite3` 命令行时，也可以先执行 `sqlite3 data/platforms.sqlite3` 再粘贴 SQL。

先查找目标平台，并把示例中的平台名称换成真实名称：

```sql
SELECT id, name, country
FROM platforms
WHERE name = '平台名称';
```

### 7.1 第 1 张：本地图片并设为主图

1. 将图片文件放入 `static/img/platforms/` 的子目录，例如：

   ```text
   static/img/platforms/platform-name/official-side.jpg
   ```

2. 数据库只保存相对于 `static/` 的路径，即 `img/platforms/platform-name/official-side.jpg`。用事务先清除旧主图状态，再插入新主图：

```sql
BEGIN IMMEDIATE;

UPDATE platform_images
SET is_primary = 0
WHERE platform_id = (SELECT id FROM platforms WHERE name = '平台名称');

INSERT INTO platform_images (
    platform_id, local_path, caption, source_url, source_name,
    image_type, is_primary, sort_order
)
SELECT
    id,
    'img/platforms/platform-name/official-side.jpg',
    '官方侧视图',
    'https://www.example.org/platform-page',
    '厂商官网',
    'official',
    1,
    10
FROM platforms
WHERE name = '平台名称';

COMMIT;
```

### 7.2 第 2 张：网络图片

```sql
INSERT INTO platform_images (
    platform_id, image_url, caption, source_url, source_name,
    image_type, is_primary, sort_order
)
SELECT
    id,
    'https://images.example.org/platform-name/exercise.jpg',
    '演习期间的海上航行画面',
    'https://www.example.org/exercise-report',
    '演习新闻稿',
    'exercise',
    0,
    20
FROM platforms
WHERE name = '平台名称';
```

### 7.3 第 3 张：另一张本地图片

先把文件放到 `static/img/platforms/platform-name/loading.jpg`，再执行：

```sql
INSERT INTO platform_images (
    platform_id, local_path, caption, source_url, source_name,
    image_type, is_primary, sort_order
)
SELECT
    id,
    'img/platforms/platform-name/loading.jpg',
    '任务载荷装载画面',
    'https://www.example.org/loading-report',
    '项目新闻稿',
    'loading',
    0,
    30
FROM platforms
WHERE name = '平台名称';
```

完成后刷新平台档案页，主图下方会出现三张缩略图。

### 7.4 把另一张图设为主图

先找到图片 ID：

```sql
SELECT id, caption, image_url, local_path, is_primary, sort_order
FROM platform_images
WHERE platform_id = (SELECT id FROM platforms WHERE name = '平台名称')
ORDER BY is_primary DESC, sort_order, id;
```

假设要将图片 `id = 25` 设为主图。唯一索引保证每个平台最多一张主图，所以务必在同一事务中先清零、再设置：

```sql
BEGIN IMMEDIATE;

UPDATE platform_images
SET is_primary = 0
WHERE platform_id = (SELECT id FROM platforms WHERE name = '平台名称');

UPDATE platform_images
SET is_primary = 1
WHERE id = 25
  AND platform_id = (SELECT id FROM platforms WHERE name = '平台名称');

COMMIT;
```

最后复核：

```sql
SELECT id, caption, is_primary, sort_order
FROM platform_images
WHERE platform_id = (SELECT id FROM platforms WHERE name = '平台名称')
ORDER BY is_primary DESC, sort_order, id;
```

### 7.5 图片路径与来源规则

- 本地图片统一放在 `static/img/platforms/`；数据库路径以 `img/platforms/` 开头。
- `local_path` 使用 `/`，省略 `static/`、盘符和开头的 `/`，也避免 `..` 路径段。
- 网络图片 `image_url` 与出处 `source_url` 均填写完整的 `http://` 或 `https://` URL。
- 一条记录通常在 `image_url` 与 `local_path` 中选择一种；两者同时存在时页面优先使用网络图片。
- 图片来源建议指向承载原图或明确说明图像出处的网页，并填写易读的 `source_name` 与 `caption`。
- 网络图片可能受源站迁移或防外链策略影响；获准保存的图片放入本地目录，展示会更稳定，同时仍保留 `source_url` 便于核验。

## 8. 当前图片状态

现有两份 Excel 资料没有附带可复用、已经核验出处的装备照片，因此默认数据库暂未写入平台实拍图。页面会统一显示：

```text
static/img/placeholder-platform.svg
```

占位图内明确写有“平台图片待补充 / PLACEHOLDER”，只表示当前缺少经核验图片，绝非装备实拍图。这样可以避免用随机船艇照片代替具体型号，也避免给图片来源核验造成混淆。按上一节补录图片后，卡片、列表、档案和对比页会自动使用新图片。

## 9. 运行自动测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试覆盖：

- 22 型平台的双工作簿原子导入、分来源重复导入与冲突回滚；
- 各标签、批次、证据等级及 `unrated` 的筛选数量；
- 关键词、组合筛选、URL 状态与模板转义；
- 22 个档案页、未达 E2 徽章、缺失值和原文入口；
- 单图 / 多图顺序、危险 URL 与越界本地路径处理；
- 2、3、4 型平台对比及异常参数；
- 重复导入后图片保留；
- 数据库迁移的幂等性和旧表保留；
- 首页统计数字随数据库变化。

## 10. 数据口径

- **L**：补给运输；**L/W**：补给与武器载荷；**W**：作战载荷。标签沿用原表。
- **E2**：确认参演；**E3**：演习中执行任务；**E4**：实际军事部署；**E5**：公开实战使用。
- **未达 E2 / 未评级**：现有资料仅支持公开展示、海试、研发等记录时，`evidence_code` 保持为空；页面明确显示“未达E2”，也不会将其计入 E2。
- 第二批强调“平台能力资料”与活动、试验或公开展示记录可能来自不同来源或不同活动，详情页会显示提示并保留各自来源。
- 性能值保留原表单位、范围和限定词；“未公开”等缺失值在页面显示为 `—`。
- 来源分为性能、活动、操控 / 任务三类。外部链接在导入和渲染阶段都只接受 HTTP / HTTPS。
- `Splash Typhoon` 保留 2026-09-22 的复核备注：原表引用的厂商 LinkedIn 简介与厂商官网当前公开航程存在口径差异，两条入口均保留供人工核验。

## 11. Classimax 与第三方说明

目录卡片、紧凑列表、筛选侧栏和详情双栏等**组件结构与信息层级**参考了 Themefisher 的 [Classimax Bootstrap](https://github.com/themefisher/classimax-bootstrap)。本项目将这些模式重新实现为 Flask / Jinja 模板、自有 CSS 与原生 JavaScript。

项目没有复制 Classimax 演示图片，也没有引入其分类广告内容、价格、评分、卖家、支付、地图或 jQuery 插件。Classimax 代码采用 MIT 许可证；上游许可证副本与归属信息分别保存在：

- `THIRD_PARTY_NOTICES.md`
- `LICENSES/Classimax-MIT.txt`

添加新图片时，请同时记录原始网页入口、图片说明与来源名称，以便后续逐图核验来源和使用条件。

## 12. 当前限制与后续优化

- 当前两份工作簿没有附带已经核验许可与出处的装备照片，因此正式数据库仍使用明确标注的统一占位图；需按第 7 节逐图补录。
- 活动记录已经拆成一对多时间线，但来源目前仍按“平台 + 用途”关联；若要精确做到一条事件对应一条来源，可增加活动—来源关联表。
- 性能仍以来源原文文本保存，适合核验但不适合自动数值排序；后续可另加规范化数值字段，同时继续保留原文。
- 本版没有登录、后台管理、在线编辑、自动爬虫或多用户审批；维护通过导入脚本、migration 和图片 CLI 完成。
- `app.py` 启动的是 Flask 本地开发服务器，适合本机研究展示；若公开部署，需另配生产 WSGI 服务、反向代理、备份与访问控制。

## 13. 常见问题

### `migrate.py` 提示数据库不存在

这是一个全新数据库路径时，先运行一次 `import_data.py --db 路径`；它会从 `schema.sql` 建立完整结构。迁移脚本用于升级已经存在的数据库。

### 图片文件存在，但页面仍显示占位图

依次检查：

1. 文件是否位于 `static/img/platforms/`；
2. `local_path` 是否写成 `img/platforms/...`；
3. 路径是否包含盘符、开头 `/` 或 `..`；
4. 平台 ID 是否对应正确；
5. 浏览器是否仍缓存旧页面，可使用 `Ctrl+F5` 强制刷新。

### 网络图片加载后又消失

源站可能更换地址或启用防外链。先打开 `image_url` 和 `source_url` 核验；具备保存条件时，将图片放入 `static/img/platforms/` 并改用 `local_path`。

### 5000 端口已被占用

换一个端口启动：

```powershell
.\.venv\Scripts\python.exe -m flask --app app run --host 127.0.0.1 --port 5001
```

随后打开 <http://127.0.0.1:5001/>。
