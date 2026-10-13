# 课程要求对应说明

依据用户提供的三张 Simple Workflow MVP 课程截图整理。截图中的内容视为项目要求，不授权课程平台提交、远程发布或账号操作。

| 要求 | 项目对应 | 证据 |
| --- | --- | --- |
| 至少两个 Agent 协作 | 分析、文档、审校共三个独立角色 | docflow/agents.py；运行记录 messages |
| Agent 消息传递或状态共享 | Message 协议 + WorkflowState | docflow/models.py；界面消息页签 |
| 基本顺序流程控制 | analyzer → writer → reviewer | docflow/workflow.py；日志顺序 |
| MVP 可运行 | 无第三方依赖，Windows 启动入口和本地界面 | start.bat、README；接口端到端测试 |
| 条件分支、循环（推荐） | 审校不通过返回 writer，最多一次自动修订 | 审校修订与修订上限测试 |
| 可视化（可选） | 三节点状态、结果页签、历史、日志 | static/；界面截图 |
| 日志与追踪（推荐） | 节点日志、消息载荷、请求元数据、JSON 导出 | evidence/deepseek-demo/trace.json |
| 错误处理、恢复（推荐） | 检查点保存、失败节点重试、重启中断标记 | 恢复测试；StateStore |
| 复用项目 1（允许） | 未提供项目 1，采用独立设计 | Design.md |
| 完整性 40% | 输入源码到文档和审校的完整链路 | 真实 DeepSeek 调用及 API 端到端测试 |
| 协作 30% | 分析事实、草稿与审校反馈的明确交接 | messages、节点 outputs、attempts |
| 可扩展性 20% | 统一 Agent 接口，编排器可替换节点列表 | 扩展测试与 Design 第 9 节 |
| 文档 10% | 项目说明、架构、流程图、测试与演示稿 | README.md、Design.md、docs/ |
| 源码提交 | 整个项目源码及压缩包 | DocFlow_提交包.zip |
| README / Design | 两份中文 Markdown 已提供 | README.md、Design.md |
| 1 分钟视频（可选） | 提供一分钟讲解与操作脚本，未录制视频 | docs/Demo.md |
| 小于 200 MB，学号姓名命名 | 压缩包体积会在交付时检查，提交前自行改为学号姓名 | 提交包；README |

不代填姓名学号，不代提交课程平台；文件交付即完成本次制作范围。
