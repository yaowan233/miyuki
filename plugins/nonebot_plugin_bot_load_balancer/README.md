# NoneBot Plugin: Bot Load Balancer

一个完全独立的、零侵入式的 Bot 负载均衡插件，适用于 NoneBot2。

## 特性

- **智能负载均衡**：根据账号最小回复间隔、最近发言频率和群内轮询自动分摊回复
- **零侵入性**：通过 Monkey Patch 机制改写 NoneBot 的事件分发入口，无需修改任何现有插件代码
- **完全解耦合**：独立的数据存储（`BotMessageStats` 表），不修改任何现有表结构
- **支持所有插件**：包括第三方 pip 安装的插件（如 `nonebot-plugin-osubot`）
- **粘性会话**：可配置同一会话优先使用上次使用的 Bot
- **自动清理**：定期清理超时的统计数据

## 工作原理

### 负载均衡算法

```python
先过滤掉仍在最小回复间隔内的 Bot
再选择当前群里最近时间窗口内发言次数最少的 Bot
若并列，则在并列 Bot 之间轮询
```

### Monkey Patch 拦截机制

1. 收到群事件时，在事件分发入口选择当前会话最合适的 Bot
2. 使用选中的 Bot 运行整个 matcher 生命周期
3. 之后 `current_bot`、`matcher.send()`、`UniMessage.send()` 都会落到同一个 Bot
4. 发送后更新该 Bot 在当前群的最近发言统计

这种机制对所有插件完全透明，包括：
- 内置插件
- 自定义插件
- 第三方 pip 安装的插件

## 安装

将插件目录复制到 `plugins/` 目录下：

```bash
plugins/
├── nonebot_plugin_bot_load_balancer/
│   ├── __init__.py
│   ├── config.py
│   ├── model.py
│   ├── balancer.py
│   ├── interceptor.py
│   ├── migrations/
│   │   └── a1b2c3d4e5f6_init_bot_message_stats.py
│   └── README.md
```

## 配置

在 `.env` 文件中添加以下配置项（所有配置项都是可选的）：

```ini
# 是否启用负载均衡（默认：true）
bot_load_balancer__enabled=true

# 统计时间窗口，单位：分钟（默认：10）
bot_load_balancer__time_window=10

# 单个 Bot 的最小回复间隔，单位：秒（默认：2.0）
bot_load_balancer__min_reply_interval=2.0

# 是否启用粘性会话（默认：true）
# 启用后，同一群组会优先使用上次使用的 Bot
bot_load_balancer__sticky_session=true

# 自动清理间隔，单位：秒（默认：300）
bot_load_balancer__cleanup_interval=300
```

## 数据库迁移

插件使用独立的 `BotMessageStats` 表存储统计数据。

### 表结构

```sql
CREATE TABLE bot_message_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id VARCHAR(64) NOT NULL,           -- Bot 的 self_id
    session_id VARCHAR(64) NOT NULL,       -- 群组 ID 或私聊 ID
    message_count INTEGER NOT NULL,        -- 消息计数
    last_message_time DATETIME NOT NULL,   -- 最后发言时间
    active_tasks INTEGER NOT NULL,         -- 活跃任务数
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    
    INDEX idx_bot_id (bot_id),
    INDEX idx_session_id (session_id),
    INDEX idx_last_message_time (last_message_time),
    UNIQUE INDEX idx_bot_session (bot_id, session_id)
);
```

### 执行迁移

迁移文件已经包含在插件中，NoneBot 启动时会自动执行迁移。

如果需要手动执行迁移：

```bash
# 使用 nonebot-plugin-orm
nb orm upgrade head
```

## 使用方法

### 自动启用

插件会在 NoneBot 启动时自动初始化，并自动改写事件分发入口。

无需在其他插件中做任何修改！所有插件（包括第三方插件）都会自动享受负载均衡。

### 禁用插件

在 `.env` 中设置：

```ini
bot_load_balancer__enabled=false
```

或者完全删除/重命名插件目录。

## 监控和调试

插件会输出详细的日志信息：

```
[Bot Load Balancer] Starting up...
[Bot Load Balancer] Plugin enabled
[Bot Load Balancer] Bot 123456 connected
[Bot Load Balancer] Successfully patched event dispatch
[Bot Load Balancer] Bot 123456: recent_count=5, since_last_reply=12.4, score=5.00
[Bot Load Balancer] Bot 789012: recent_count=3, since_last_reply=1.2, score=3.00
[Bot Load Balancer] Selected bot 123456 for session 987654321 (score: 7.00)
[Bot Load Balancer] Recorded assignment for bot 123456 in 987654321 (total events: 6)
```

## 高级功能

### 手动控制

虽然插件是完全自动的，但如果需要，你也可以手动控制：

```python
from plugins.nonebot_plugin_bot_load_balancer import get_balancer, get_interceptor

# 获取负载均衡器实例
balancer = get_balancer()

# 手动选择 Bot
selected_bot = await balancer.select_bot("123456789")

# 获取统计信息
stats = await balancer.get_stats("123456789")

# 重置统计信息
await balancer.reset_stats("123456789")  # 重置特定会话
await balancer.reset_stats()             # 重置所有会话

# 获取拦截器实例
interceptor = get_interceptor()

# 手动给事件分发入口打补丁
interceptor.patch_handle_event()

# 取消补丁
interceptor.unpatch_handle_event()
```

### 定时清理

如果安装了 `nonebot-plugin-apscheduler`，插件会自动启用定时清理功能：

```bash
nb plugin install nonebot_plugin_apscheduler
```

清理任务会根据 `cleanup_interval` 配置定期运行。

## 架构设计

### 完全解耦合

- **独立数据表**：使用 `BotMessageStats` 表，不修改任何现有表
- **独立配置**：所有配置项使用 `bot_load_balancer__` 前缀
- **独立逻辑**：所有负载均衡逻辑都在独立插件中

### 零侵入性

- **不修改现有代码**：通过 Monkey Patch 实现，无需修改任何现有插件
- **透明拦截**：拦截事件分发入口，对插件完全透明
- **兼容所有插件**：包括第三方 pip 安装的插件

### 核心组件

1. **config.py**：配置类，使用 pydantic BaseModel
2. **model.py**：`BotMessageStats` 数据模型，使用 nonebot_plugin_orm
3. **balancer.py**：负载均衡器核心逻辑，实现智能选择算法
4. **interceptor.py**：Monkey Patch 拦截器，拦截事件分发入口
5. **__init__.py**：插件入口，注册所有钩子

## 常见问题

### Q: 如何确认插件已启用？

A: 查看启动日志，应该看到：

```
[Bot Load Balancer] Plugin enabled
[Bot Load Balancer] Successfully patched event dispatch
```

### Q: 插件会影响性能吗？

A: 影响极小。负载均衡逻辑只在需要时才执行（群消息且有多个同平台 Bot），并且主要基于轻量级的内存冷却和单次数据库查询。

### Q: 如何禁用特定群的负载均衡？

A: 目前插件不支持按群禁用。如果需要此功能，请修改 `interceptor.py` 中的 `_should_balance()` 方法。

### Q: 支持私聊负载均衡吗？

A: 目前只支持群聊负载均衡。私聊消息不会被拦截。

### Q: 如何卸载插件？

A: 
1. 在 `.env` 中设置 `bot_load_balancer__enabled=false` 并重启
2. 删除或重命名 `plugins/nonebot_plugin_bot_load_balancer/` 目录
3. （可选）清理数据库：`DROP TABLE bot_message_stats;`

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License
