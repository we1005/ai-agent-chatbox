# Celery 异步向量化 · 运维与使用手册

> 📐 设计决策与架构详见 [`analysis-for-backend/celery-module.md`](../analysis-for-backend/celery-module.md)
> 🗺️ 落地 plan 见 [`plan-doc-dir/quizzical-spinning-parrot.md`](../plan-doc-dir/quizzical-spinning-parrot.md)
>
> 本文只讲**怎么用**、**怎么调**、**怎么排错**。

---

## 1. 为什么引入

原先上传知识库文档后：

```python
# backend/app/services/rag_service.py
asyncio.create_task(self._vectorize_document(filename_on_disk))
```

三个问题：

1. **无限流** — 同一秒上传 10 份 PDF 就 10 个 `asyncio.to_thread` 并发，线程池 / GPU 容易炸
2. **与主进程共命运** — backend 重启，processing 中的任务就丢了
3. **无持久队列 / 监控** — 排队、重试、失败死信、进度全不可见

**本次方案**：引入 Celery + Redis，**默认 off** 完全向后兼容；开启后走队列 + worker，并发由 `--concurrency=N` 一键控制；Redis AOF 持久化，backend 重启队列不丢。

---

## 2. 核心架构：Worker 不持有模型

**削峰填谷的本质** = 限流 + 持久队列，不是"算力搬家"。所以 worker 容器 **不加载 BGE-M3**，只做 HTTP 转发。

```
upload → backend → task.delay(file_id) → Redis queue
                                              ↓
                                    Celery Worker (~100MB Docker)
                                    concurrency=2 ← 水龙头开度
                                              ↓
                              HTTP POST /api/internal/vectorize
                                              ↓
                            backend 的 _do_vectorize_sync()
                              BGE-M3 仅主进程加载一份
```

**收益**：
- Worker 容器镜像 ~100MB（vs 自带模型要 ~3GB），启动秒级
- BGE-M3 全栈只加载一份，与 classic RAG 召回共享
- 削峰阀门 = worker `--concurrency=2`（想更保守调成 1）
- `/api/internal/*` 中间件只允许本机 IP，外网不可达

---

## 3. 首次启动（一次性准备）

```bash
# 0. 前提：已装 Redis（brew install redis）+ Docker + Python venv
cd backend && source venv/bin/activate
pip install -r requirements.txt   # 会装新增的 celery + redis

# 1. 开启 Redis AOF（备份原 conf → 追加 AOF → brew services restart → 验证）
bash start-redis-with-aof.sh

# 2. 构建并启动 worker + Flower 两个容器
docker compose -f docker-compose.celery.yml up -d --build

# 3. 确认 worker ready
docker logs xuanjian-celery-worker | grep ready
# 应看到：celery@<container_id> ready.
```

---

## 4. 日常启动（后续每次开发）

Redis 和 Docker 容器如果已经在跑，不用重启。否则：

```bash
# 启 Redis（如果已跑则跳过）
brew services start redis

# 启 Docker worker + Flower（如果已跑则跳过）
cd backend && docker compose -f docker-compose.celery.yml up -d

# 启 backend
source venv/bin/activate
cd backend && uvicorn main:app --reload --reload-dir app

# 启 frontend
cd frontend && npm run dev
```

浏览器访问 `http://localhost:5173/admin/infra` → 确认三张卡全绿 → 点亮 Celery toggle（开启前会自动预检）。

---

## 5. 验证 & 调试

### 5.1 三层健康检查

```bash
# Redis
redis-cli ping                  # → PONG
redis-cli CONFIG GET appendonly # → yes

# Celery worker
docker logs xuanjian-celery-worker --tail 20
docker exec xuanjian-celery-worker celery -A app.workers.celery_app inspect ping

# Flower
curl -u admin:xuanjian http://localhost:5555/api/workers | jq
```

### 5.2 后端健康端点（前端 AdminInfra 页也是调这个）

```bash
curl http://localhost:8000/api/embedding/celery/health | jq
```

返回：
```json
{
  "redis":  { "ok": true,  "ping_ms": 0.7, "error": null },
  "celery": { "ok": true,  "workers": 1, "worker_names": ["celery@..."], "error": null },
  "flower": { "ok": true,  "url": "http://localhost:5555", "error": null }
}
```

### 5.3 端到端 task 测试

```bash
source venv/bin/activate
python -c "
from app.workers.tasks import vectorize_document
r = vectorize_document.delay('not-a-real-file-id')
print(f'task id = {r.id}')
print(f'state = {r.state}')
"
```

观察：
- 初始 `PENDING` → 被 worker 取走 → HTTP 请求 backend → 404（文件不存在）→ autoretry 3 次 → `FAILURE`
- Flower 监控页 `http://localhost:5555/tasks` 能看到这条 task 记录

### 5.4 看 Flower 监控

```
http://localhost:5555          仪表盘
http://localhost:5555/workers  活跃 worker 列表 + Load Average
http://localhost:5555/tasks    所有任务历史（含 Active / Processed / Failed / Retried）
http://localhost:5555/broker   Redis 队列状态
账号：admin  密码：xuanjian
```

---

## 6. API 契约

| 方法 | 路径 | 用途 |
|------|------|------|
| `GET` | `/api/embedding/celery` | 查询开关状态 |
| `PUT` | `/api/embedding/celery` | 切换开关；`body: {"enabled": true/false}`。开启前自动预检，失败 503 + 详情 |
| `GET` | `/api/embedding/celery/health` | Redis / Worker / Flower 三项健康 |
| `POST` | `/api/internal/vectorize/{file_id}` | 内部端点 · 仅本机可达 · worker 回调专用 |

切换开关的 CLI 示例：

```bash
# 开启
curl -X PUT http://localhost:8000/api/embedding/celery \
  -H 'Content-Type: application/json' \
  -d '{"enabled": true}'

# 关闭（立即回到 asyncio.to_thread 路径）
curl -X PUT http://localhost:8000/api/embedding/celery \
  -H 'Content-Type: application/json' \
  -d '{"enabled": false}'
```

---

## 7. 关闭 / 回退

### 7.1 只关 Celery（保留 Docker 容器待命）

前端 `/admin/infra` 关掉 toggle → 立即回到 `asyncio.to_thread` 路径。**零破坏**。

### 7.2 彻底停止 Docker 容器

```bash
cd backend
docker compose -f docker-compose.celery.yml down
# 或 docker compose -f docker-compose.celery.yml stop  （保留容器，下次快速 start）
```

### 7.3 回退 Redis AOF 配置（一般不用）

```bash
# 脚本会自动备份为 redis.conf.bak.TIMESTAMP
ls /opt/homebrew/etc/redis.conf.bak.*
cp /opt/homebrew/etc/redis.conf.bak.<最早的时间戳> /opt/homebrew/etc/redis.conf
brew services restart redis
```

---

## 8. 文件结构速查

```
backend/
├── CELERY.md                      ← 本文件
├── redis.conf                     推荐 Redis 配置（AOF everysec）
├── start-redis-with-aof.sh        一键开启 Homebrew Redis AOF
├── Dockerfile.celery              worker 镜像 · ~100MB
├── docker-compose.celery.yml      worker + flower 两服务
├── requirements.celery.txt        worker 容器独立依赖（celery+redis+requests）
├── app/
│   ├── workers/
│   │   ├── celery_app.py          Celery app 工厂
│   │   └── tasks.py               vectorize_document(file_id) · HTTP 转发
│   ├── api/
│   │   ├── api.py                 注册 internal router
│   │   └── endpoints/
│   │       ├── embedding.py       +/api/embedding/celery(/health)
│   │       └── internal.py        +POST /api/internal/vectorize/{file_id}
│   ├── services/
│   │   ├── embedding_service.py   EmbeddingConfig.celery_enabled=False
│   │   └── rag_service.py         upload_document 加 celery 分支
│   └── models/
│       └── knowledge_document.py  +celery_task_id 字段
└── main.py                        +/api/internal/* 中间件 + 重启恢复分支
```

---

## 9. 配置项

### `backend/data/embedding_config.json`

开关状态存这里：

```json
{
  "celery_enabled": true
}
```

通过 `PUT /api/embedding/celery` 修改即可，无需手动编辑。

### `backend/app/workers/celery_app.py`

环境变量驱动（默认值已内置，一般不用改）：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | broker；worker 容器会被覆盖为 `host.docker.internal:6379/0` |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/1` | 结果存 db1，避免污染 broker |
| `BACKEND_URL` | `http://localhost:8000` | worker 回调地址；容器里覆盖为 `host.docker.internal:8000` |

### `backend/docker-compose.celery.yml`

- `concurrency=2` 削峰阀门（调高更激进，调低更保守）
- `mem_limit: 512m` worker · `256m` flower
- Flower basic auth：`admin:xuanjian`（只绑 :5555，本机访问，够用）

---

## 10. 故障排查

| 症状 | 原因 | 解决 |
|---|---|---|
| `AdminInfra` Redis 卡红：`ConnectionRefused` | Redis 未启动 | `brew services start redis` |
| Worker 卡红：`no workers alive` | Docker 容器未启 / Redis 连不上 | `docker compose up -d`；若 worker 日志 `Connection refused` 则主机 Redis 没起 |
| Flower 卡红：`ConnectionRefused :5555` | Flower 容器未启 / 端口冲突 | `docker ps \| grep flower`；查端口 `lsof -i :5555` |
| toggle 开启 503：`Celery 未就绪` | Redis 或 worker 预检失败 | 按错误提示里的 `health` 字段排查 |
| Task 卡在 `PENDING` 很久 | Worker 没消费 / Redis db 搞错 | `docker logs xuanjian-celery-worker`；确认 `CELERY_BROKER_URL` 跟 client 一致 |
| Task 全部 `FAILURE`：`Connection refused :8000` | Worker 容器连不上 backend | Mac/Win 应该自动支持 `host.docker.internal`；Linux 检查 `extra_hosts` 生效 |
| `/api/internal/*` 被中间件 403 | worker 源 IP 不在白名单 | 查 backend 日志看 `client_ip`；白名单涵盖 127.0.0.1 / 172.x / 192.168.x / 10.x，按需扩 |
| 向量化很慢 | BGE-M3 是 CPU 模式 / 文档太大 | 查 `/api/embedding/system-info` 确认 GPU；加大 worker concurrency 对 CPU 密集无助 |
| 任务丢了 | Redis 没开 AOF + 断电 | `redis-cli CONFIG GET appendonly` 必须返 `yes`；重跑 `start-redis-with-aof.sh` |

---

## 11. 重启语义

`main.py::_recover_stuck_vectorizations` 启动时按下面顺序恢复：

1. 查所有 `vectorize_status == "processing"` 的文档
2. 若 `celery_enabled`：通过 `celery_app.control.inspect()` 取 active + reserved + scheduled 任务 id 集合
3. 对每份 stuck doc：
   - 文件已丢失 → 标 failed
   - `celery_task_id` 还在 active set → 跳过（任务还在跑）
   - 否则 → celery on 时重新 `.delay()`；off 时走 `asyncio.create_task`

**结论**：backend 重启**不会**把 Redis 里活着的任务重复入队；Redis 挂了（或 AOF 没开又断电）才会真丢。

---

## 12. 设计文档 · 延伸阅读

- 💡 架构决策 & 选型：[`analysis-for-backend/celery-module.md`](../analysis-for-backend/celery-module.md)
- 📋 实施 plan：[`plan-doc-dir/quizzical-spinning-parrot.md`](../plan-doc-dir/quizzical-spinning-parrot.md)
- 🗺️ 可视化架构：[`http://localhost:5173/wiki/architecture`](http://localhost:5173/wiki/architecture)（"基础设施" 子模块 · 未来版本加入）
