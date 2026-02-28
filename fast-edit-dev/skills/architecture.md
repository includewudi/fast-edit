---
name: architecture
description: V0/V1 engine、scheduler、PagedAttention 架构说明
---

# Architecture

> 面向高吞吐推理场景的架构说明文档，覆盖 V0/V1 engine、调度器与 PagedAttention。

## 目标与边界

- **目标**：提升吞吐、降低 P99 延迟、稳定显存占用。
- **边界**：专注推理执行链路，不包含训练、模型微调与权重分发。

## 高层结构

```
客户端请求
   │
   ▼
┌──────────────┐      ┌────────────────────┐      ┌────────────────────┐
│  Frontend    │─────▶│  Scheduler (V1)    │─────▶│  Execution Engine  │
│  (API/CLI)   │      │  预填充/解码队列    │      │  V0/V1 Pipeline     │
└──────────────┘      └────────────────────┘      └────────────────────┘
                                                       │
                                                       ▼
                                                ┌──────────────┐
                                                │PagedAttention│
                                                │ KV Cache 管理 │
                                                └──────────────┘
```

## 组件地图

| 组件 | 角色 | V0 | V1 | 关键指标 |
|---|---|---|---|---|
| V0 Engine | 直线执行引擎 | ✅ | ❌ | latency | 
| V1 Engine | 任务分段执行 | ❌ | ✅ | throughput | 
| Scheduler | 预填充/解码调度 | ❌ | ✅ | batch size | 
| PagedAttention | KV Cache 分页 | ❌ | ✅ | memory usage | 
| Frontend | API/CLI/协议适配 | ✅ | ✅ | QPS | 
| Metrics | 追踪与告警 | ✅ | ✅ | P95/P99 | 

## V0 Engine（线性执行）

### 执行流程

```
Request -> Tokenize -> Prefill -> Decode (loop) -> Stream
```

### 特征

- **简单**：单请求直线执行，调试成本低
- **低并发**：批处理能力弱，吞吐受限
- **显存波动**：KV cache 生命周期与请求绑定

### 适用场景

| 场景 | 是否推荐 | 原因 |
|---|---|---|
| 单请求、低并发 | ✅ | 复杂度最低 |
| 多用户并发 | ❌ | 调度缺失导致排队严重 |
| 长上下文 | ❌ | KV cache 无法分页 |

## V1 Engine（调度 + 分页）

### 核心思想

- **拆分执行阶段**：Prefill 与 Decode 分离
- **队列化调度**：每个请求在不同阶段排队
- **分页缓存**：KV cache 以 page 为粒度复用与回收

### 关键流程

```
Request
  ├─> Prefill Queue  ──┐
  │                   │ batch
  └─> Decode Queue  <─┘  token-step
```

### V1 Pipeline 步骤

1. 解析请求 → 生成调度任务
2. Prefill 批量执行 → 生成 KV blocks
3. Scheduler 按 token-step 调度解码
4. 输出流式返回，直到 EOS

## Scheduler（调度器）

### 设计目标

- **吞吐最大化**：批大小优先于单请求延迟
- **公平性**：长请求不得饿死短请求
- **可抢占**：高优先级请求可插队

### 阶段划分

| 阶段 | 描述 | 输入 | 输出 |
|---|---|---|---|
| Prefill | 一次性上下文填充 | prompt tokens | KV blocks | 
| Decode | 每步生成 1 token | KV blocks | token stream |

### 调度循环（简化伪码）

```python
while True:
    ready = prefill_queue.pop(max_batch=prefill_batch)
    if ready:
        run_prefill(ready)
        decode_queue.extend(ready)

    decode_batch = decode_queue.pop(max_batch=decode_batch)
    if decode_batch:
        run_decode_step(decode_batch)
```

### 队列策略

- **Prefill Queue**：按到达时间排序，优先批量化
- **Decode Queue**：Round-robin + 优先级权重
- **Timeout 回收**：超过阈值的请求进入降级通道

### 状态机

```
NEW -> PREFILL -> DECODE -> FINISHED
          │          │
          └──ERROR───┘
```

## PagedAttention（KV 分页）

### 背景问题

- **传统 KV Cache**：按请求分配连续显存，碎片化严重
- **长上下文**：缓存膨胀，显存不可预测

### 设计要点

| 要点 | 说明 | 收益 |
|---|---|---|
| 固定 page size | KV 以页为单位 | 降低碎片 |
| Block Table | 逻辑→物理映射 | 支持迁移 | 
| 共享空闲池 | 回收空闲页 | 提高利用率 | 
| LRU 回收 | 优先释放长尾 | 降低峰值 |


### 数据结构

```
RequestState
  └─ block_table: [page_id, page_id, ...]

PagedKVCache
  ├─ free_pages
  ├─ allocated_pages
  └─ page_size
```

### 写入流程

```
for token in new_tokens:
    page = kv_cache.allocate_page()
    write_kv(page, token)
    block_table.append(page)
```

### 读写路径

| 路径 | 操作 | 关键点 |
|---|---|---|
| Prefill | 批量写入 | 连续页分配 | 
| Decode | 随机读写 | block_table 查找 | 

## 执行与资源模型

### 关键资源

| 资源 | 说明 | 影响 |
|---|---|---|
| GPU SM | 并行执行单元 | decode throughput |
| HBM | 显存容量 | context length |
| PCIe/NVLink | 传输带宽 | prefill latency |

### 资源放大因子

```
吞吐 ~= batch_size * (tokens/sec per GPU)
显存 ~= (context_len * hidden_size * 2) / page_size
```

## 故障与降级策略

| 触发条件 | 影响 | 降级动作 |
|---|---|---|
| 显存耗尽 | OOM | 降低 batch / 缩短 context |
| 长尾请求 | 阻塞队列 | 提前终止 / 低优先级 | 
| 过载 | 排队时间变长 | 限流 + 拒绝策略 |

## Metrics & Observability

### 核心指标

- **Prefill time**
- **Decode time / token**
- **Scheduler wait time**
- **KV cache hit ratio**
- **GPU memory watermark**

### 事件追踪

```
request_id -> prefill_start -> prefill_end -> decode_start -> finish
```

## 文件结构映射（对本仓库）

> 注意：当前仓库是 fast-edit 工具，没有实际推理引擎。以下是架构映射示意，便于后续扩展。

| 模块 | 类/函数 | 责任 | 对应架构角色 |
|---|---|---|---|
| fast_edit.py | main(), parse_content | CLI 入口 | Frontend |
| core.py | write_file(), read_lines() | 原子 I/O | Runtime core |
| edit.py | replace(), batch() | 编辑执行 | Engine | 
| paste.py | paste(), write() | IO adapter | Frontend | 
| generate.py | generate() | 批量生成 | Scheduler | 
| verify.py | verify(), restore() | 回滚验证 | Control plane |

## 约束与演进路线

- **V0**：单进程直线式执行，优先正确性
- **V1**：任务切片 + 调度器 + KV 分页
- **V2（规划）**：多 GPU 调度 + 跨节点 cache

## 写作规范（大文件分段生成）

```
1. 先写脚本文件分段保存
2. 最后执行脚本生成目标文件
3. 避免一次性 heredoc 输出超长内容
```

