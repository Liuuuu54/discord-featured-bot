# 书单发布接口（Booklist Publish API）

供 **webpage 后端**在校验用户身份与书单归属后，server-to-server 转发「发布到 Discord」请求，
由 dc_bot 在目标论坛帖内发出（或更新）一条书单 embed 消息。

- 实现：[`app/booklist/api.py`](../app/booklist/api.py)（aiohttp，与 bot 同进程同事件循环）
- 信任模型：webpage 后端负责认证用户、确认书单归属；本接口只校验共享密钥 + Discord 侧的帖主身份。前端不直接调用。

---

## 启用与配置

通过环境变量配置（见 [`config.py`](../config.py)）。**安全默认：默认不启用；即使启用，未设置密钥也不会启动。**

| 变量 | 默认 | 说明 |
|---|---|---|
| `BOOKLIST_API_ENABLED` | `false` | 设为 `true` 才启动接口 |
| `BOOKLIST_API_SECRET` | （空） | 与 webpage 后端约定的共享密钥；**为空则接口不启动** |
| `BOOKLIST_API_HOST` | `0.0.0.0` | 监听地址 |
| `BOOKLIST_API_PORT` | `10820` | 监听端口 |
| `BOOKLIST_API_MAX_ENTRIES` | `20` | 单条 embed 最多渲染的条目数，超出以「更多见网页」提示 |
| `BOOKLIST_WEBPAGE_URL` | `https://forum.shimmerday.top` | 「让位」时引导用户前往的网页地址（与本接口独立） |

---

## 认证

所有业务请求需带请求头：

```
X-API-Key: <BOOKLIST_API_SECRET>
```

使用常量时间比较校验。缺失或不匹配 → `401`。

---

## `GET /healthz`

健康检查，无需认证。

```json
{ "ok": true, "ready": true }
```

`ready` 为 bot 是否已连接就绪（Discord gateway）。

---

## `POST /booklist/publish`

在目标论坛帖内**发布**或**更新**一条书单 embed。

### 请求体（JSON）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `booklist_id` | int | ✅ | 网页书单 ID（幂等键之一） |
| `thread_url` | string | ✅ | `https://discord.com/channels/{guild_id}/{thread_id}` |
| `discord_user_id` | string/int | ✅ | 发布者 Discord 用户 ID；**必须等于该帖帖主** |
| `title` | string | ✅ | 书单标题 |
| `description` | string | ⬜ | 书单简介 |
| `cover_image_url` | string | ⬜ | 封面图（作为 embed thumbnail，须 http(s) 开头） |
| `items` | array | ✅ | 条目数组（可为空数组） |
| `items[].title` | string | ⬜ | 帖子标题 |
| `items[].url` | string | ⬜ | 帖子链接 |
| `items[].review` | string | ⬜ | 书单作者评价 |

示例：

```json
{
  "booklist_id": 123,
  "thread_url": "https://discord.com/channels/1375430712018210979/1400000000000000000",
  "discord_user_id": "100000000000000000",
  "title": "我的百合推荐",
  "description": "慢慢收集的几篇。",
  "cover_image_url": "https://example.com/cover.png",
  "items": [
    { "title": "某帖标题", "url": "https://discord.com/channels/.../...", "review": "很好看" }
  ]
}
```

### 成功响应 `200`

```json
{
  "ok": true,
  "updated": false,
  "message_id": "1400000000000000001",
  "message_url": "https://discord.com/channels/.../.../..."
}
```

- `updated=false`：新发的消息。
- `updated=true`：编辑了既有消息（见下方「更新语义」）。

### 错误响应

| 状态 | `error` | 含义 |
|---|---|---|
| `401` | `unauthorized` | 密钥缺失或错误 |
| `400` | `invalid json` / `missing required field...` / `invalid thread_url` / `... must be integers` / `items must be a list` / `guild mismatch` | 请求参数问题 |
| `403` | `publisher is not the thread owner` / `target is not a forum thread` / `no permission to send in thread` / `no permission to edit message` / `bot has no access to thread` | 权限/目标不符 |
| `404` | `thread not found` | 帖子不存在 |
| `502` | `fetch thread failed` / `send failed` | Discord 侧调用失败 |
| `503` | `bot not ready` | bot 尚未就绪，可稍后重试 |

错误体统一为 `{ "ok": false, "error": "<上表>" }`。

---

## `POST /booklist/unpublish`

删除网页书单在 Discord 的发布 embed（用户在网页取消发布 / 删除书单时调用）。
因为 embed 是本 bot 发的，**只有本 bot 能删**（其它 bot 无权删除他人消息）。

### 请求体（JSON）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `booklist_id` | int | ✅ | 网页书单 ID |
| `thread_url` | string | ⬜ | 指定帖：仅删该帖内的发布消息；**不传则删除该书单在所有帖的发布消息**（书单被删时用） |

### 成功响应 `200`

```json
{ "ok": true, "requested": 1, "deleted": 1 }
```

- `requested`：匹配到的发布记录数；`deleted`：实际删除/已消失的数量。
- 消息本就不存在（已被手动删）也计入 `deleted`，并停用映射，接口幂等。

### 错误响应

| 状态 | `error` | 含义 |
|---|---|---|
| `401` | `unauthorized` | 密钥缺失或错误 |
| `400` | `invalid json` / `missing required field: booklist_id` / `booklist_id must be an integer` / `invalid thread_url` | 参数问题 |
| `503` | `bot not ready` | bot 尚未就绪 |

---

## 更新语义（幂等）

每个 `(booklist_id, thread_url 对应的 thread)` 在 bot 侧只保留一条有效消息映射
（表 `webpage_published_booklists`，`UNIQUE(webpage_booklist_id, channel_id)`）。

- **首次发布**：发新消息，记录映射，`updated=false`。
- **再次以相同 `booklist_id` + 同一帖发布**：编辑既有消息，`updated=true`。
  - 因此 webpage 端「书单更新」无需独立接口——监听到书单变更后，重发本接口即可同步 embed。
- 若既有消息已被删除：自动改为新发。
- 消息被删除时（bot 监听 `message_delete`），对应映射自动停用，下次发布视为新发。

> 同一书单可发布到**不同的帖**（不同 channel），各自维护一条映射、互不影响。

---

## 校验流程（bot 侧）

1. 校验 `X-API-Key`。
2. 解析并校验请求体；解析 `thread_url` → `(guild_id, thread_id)`。
3. 取得目标频道，要求是**论坛帖**（Thread 且 parent 为 forum）。
4. 要求 `thread.owner_id == discord_user_id`（只有帖主能在本帖发布其书单）。
5. 渲染单条 embed（条目超过 `MAX_ENTRIES` 时提示前往网页）。
6. 发布或编辑消息，写入/更新映射。

---

## 待与 webpage 后端确认

- 密钥分发与轮换方式（`X-API-Key` 值）。
- 字段命名是否需要对齐（如 `items[].review` vs `comment`）。
- bot 接口对外暴露的网域/端口，以及是否经反代（建议 webpage 后端走内网或加 IP 白名单，密钥之外再加一层）。
