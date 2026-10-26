# 杞市后端（wolfberry）

枸杞交易平台后端：FastAPI + SQLAlchemy 2 + MySQL 8 + LangChain/LangGraph 风格工具层 + 腾讯云 COS。

对应需求文档：`docs/00-需求/枸杞交易平台-需求文档.md`（v4.0）
架构与目录约定：`docs/01-设计/项目规划书.md`

---

## 1. 快速开始

```bash
# 1) 依赖（独立虚拟环境）
python -m venv C:/Users/YY/.workbuddy/binaries/python/envs/wolfberry
C:/Users/YY/.workbuddy/binaries/python/envs/wolfberry/Scripts/python.exe -m pip install -r requirements.txt

# 2) 配置
copy .env.example .env.dev     # 填数据库 / JWT / COS 密钥
#（.env.dev 已在 .gitignore 中，不会提交）

# 3) 建库
mysql -h127.0.0.1 -uroot -p -e "CREATE DATABASE IF NOT EXISTS wolfberry DEFAULT CHARACTER SET utf8mb4;"

# 4) 初始化数据（用户 / 行情 / 知识库文档）
python scripts/seed.py

# 5) 演示商品（含真实图片，需要先跑过 seed）
python scripts/seed_products.py

# 6) 启动
python -m app.main             # http://127.0.0.1:8000/docs

# 7) 端到端冒烟（23 项断言）
python scripts/smoke.py
```

演示账号：`seller1 / seller123`（卖家）、`buyer1 / buyer123`（买家）、`admin / admin123`。

---

## 2. 分层与依赖方向

```
api(接口层)  →  services(业务编排)  →  domain(纯规则)  →  repositories(数据访问)  →  models(ORM)
                                     ↑
tools(智能体工具)  →  services            core(配置/日志/异常/安全)  ← 被所有层依赖，不依赖任何业务
rag(检索管线)      →  repositories(只读)
infra(数据库/存储/LLM)  ← 最底层
```

- `domain/` 不允许 import 框架（FastAPI/SQLAlchemy），保证可单测。
- `tools/` 是智能体访问业务的唯一通道；业务模块不得反向 import `tools/`。
- 规则（等级映射、定价、优化建议）全部在 `domain/`，LLM 只负责组织语言。

```
app/
├── api/v1/        # 路由：auth / products / kb / skills / system（+ 根级 files）
├── schemas/       # 请求响应 DTO
├── services/      # 用例编排、事务边界
├── domain/        # 定价规则、优化建议规则（纯函数）
├── repositories/  # SQL 查询，过滤条件全部下推
├── models/        # SQLAlchemy ORM
├── tools/         # Skill：price_suggest、product_optimize + 注册表
├── rag/           # parser → splitter → embedding → index → retriever → generator
├── infra/         # db、storage(COS/本地)、llm
└── core/          # config、errors、logging、security
```

---

## 3. 环境与密钥隔离

加载顺序（后者覆盖前者）：`.env` → `.env.<APP_ENV>` → 进程环境变量。

| 文件 | 内容 | 是否提交 |
|---|---|---|
| `.env` | 通用配置（桶名、地域、RAG 参数） | 否 |
| `.env.dev` | 开发库连接、JWT、COS 密钥 | **否（已 gitignore）** |
| `.env.example` | 模板，含全部变量说明 | 是 |

切换环境：`APP_ENV=staging` 会加载 `.env.staging`。

### 腾讯云 COS

| 变量 | 值 |
|---|---|
| `COS_BUCKET` | wolfberry-1361042049 |
| `COS_REGION` | ap-shanghai |
| `COS_DOMAIN` | wolfberry-1361042049.cos.ap-shanghai.myqcloud.com |
| `COS_SECRET_ID` / `COS_SECRET_KEY` | 控制台密钥（只放 .env.dev 或环境变量） |
| `COS_PUBLIC_READ` | false = 私有读，返回 1 小时签名 URL；true = 直接拼域名 |

`STORAGE_DRIVER=auto`（默认）：有密钥走 COS，无密钥**自动降级本地磁盘**（`var/uploads`，由 `/files/**` 提供），接口完全一致，本地开发零门槛。

---

## 4. 两个 Skill（本轮新增）

| Skill | 文件 | 作用 | 数据来源 |
|---|---|---|---|
| `price_suggest` | `tools/price_suggest.py` + `domain/pricing.py` | 三档定价建议（走量/适中/溢价）+ 偏离度 + 依据 | `market_quote` 近 30 天成交，不足自动放宽到 90 天/全国 |
| `product_optimize` | `tools/product_optimize.py` + `domain/optimize.py` | 图片质量 / 等级高报 / 缺陷率 / 置信度问题清单，按严重度排序 | 图片 L1 门禁结果 + 商品评估摘要 |

- 计算全部是规则（`domain/` 纯函数），LLM 不参与，结果可复现。
- 只读能力：不改商品、不自动定价，输出统一带免责声明。
- 调用方式：
  - 场景化端点：`POST /api/v1/skills/price-suggest`、`GET /api/v1/skills/products/{id}/optimize`
  - 通用端点：`POST /api/v1/tools/{name}/invoke`（Agent 与前端共用）
  - 清单：`GET /api/v1/tools`（按角色过滤）

---

## 5. RAG 全链路

```
上传文档(multipart) → 解析(pdf/docx/md/txt) → 切分(auto/clause/recursive/qa)
   → 向量化(DashScope text-embedding-v3 / 本地哈希兜底) → 入库(kb_chunk)
   → 检索(余弦 + 关键词加权) → 问答(带引用) → 评测(Recall@K / MRR)
```

- 上传：`POST /api/v1/kb/documents`（multipart）
- 检索：`POST /api/v1/kb/search`
- 问答：`POST /api/v1/kb/ask`（`with_llm=false` 走抽取式）
- 切片：`GET /api/v1/kb/documents/{id}/chunks`
- 评测：`GET /api/v1/kb/eval`（评测集 `scripts/eval_cases.json`）

**切分策略**（`rag/splitter.py`）：

| 策略 | 适用 | 规则 |
|---|---|---|
| `clause` | 标准/法规 | 按「第X章 / 5.2.1 / 一、」编号切，保留条款路径 |
| `recursive` | 通用长文 | 段落聚合到 500 字，重叠 80，超长段按句回退 |
| `qa` | FAQ | 按问答对切 |
| `auto` | 默认 | 编号密度 ≥3 用 clause，否则 recursive |

**效果评估**：`scripts/eval_cases.json` 共 8 题（分档标准 / 驳回流程 / 储存 / 霉变线 / 术语），
当前配置下 **Recall@5 = 1.0，MRR = 1.0**（DashScope text-embedding-v3，1024 维）。

**向量存储**：MySQL `kb_chunk.embedding`（JSON 数组）。当前规模进程内余弦足够；
换 faiss / 独立向量库时只需替换 `rag/index.py`，检索接口不变。

---

## 6. 图片素材来源

| 来源 | 文件 | 授权 | 用途 |
|---|---|---|---|
| **用户自备**（`docs/飞浆gouqi/`，185 张） | `cgcjyfyj (7).jpg`、`cgcjyfyj (37).jpg`、`cgcjyfyj (69).jpg` | 用户自有素材 | 演示商品主图 |
| Wikimedia Commons | `scripts/seed_assets/web/`（含 SOURCES.json 逐张记录作者/授权/来源页） | CC BY-SA 3.0 / 2.0 | 备选 |
| AI 生成 | `scripts/seed_assets/`（2 张） | 生成图，无版权限制 | 备选 |

- 下载脚本：`scripts/fetch_images.py`（按精确文件名拉取，可复现）。
- **注意**：用户自备图中有部分带商家水印（如"百年老店"），仅限本地演示，**上线商用前需替换为卖家自拍的原始图片**，平台侧应保留卖家上传原图的版权承诺条款。

---

## 7. 已验证（scripts/smoke.py，23/23 通过）

- 健康检查 / 登录 / 越权拦截
- 商品创建 + 图片上传（L1 门禁：低分辨率拦截）+ COS 签名 URL 外部可读
- Skill：定价建议（三档 + 偏离度）、优化建议（问题清单）、买家越权 403
- RAG：上传 → 切分（clause/qa 自动选择）→ 向量化 → 检索 → LLM 问答带引用 → Recall@5=1.0

## 8. 已知限制

1. AI 评估字段（`ai_grade/defect_ratio` 等）在演示数据中为预置值，真实值由图像评估流水线写入。
2. 向量检索为进程内计算，切片超过 50 万需换 faiss（接口已隔离）。
3. 文档入库是同步的，大文件（>100 页）建议改异步队列。
4. `order_by=defect_asc` 使用 MySQL 兼容写法 `ORDER BY defect_ratio IS NULL, defect_ratio`。
