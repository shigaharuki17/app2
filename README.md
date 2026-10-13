# DocFlow：基于 DeepSeek 的三 Agent 代码文档生成工作流

软件工程课程 Simple Workflow MVP 项目，方向为“代码 → 分析 → 文档 → 审校”。输入一份 Python 源文件，三个独立角色 Agent 协作生成中文 Markdown 文档，并留下可追踪的消息、执行日志与审校结果。

## 快速运行

需要 **Python 3.10 或更高版本**，不需要安装第三方包。

Windows 双击 `start.bat`，随后用浏览器访问 **http://127.0.0.1:8765**。

也可以在项目目录执行：

```powershell
python app.py
```

1. 点击“加载示例”，或粘贴/上传 UTF-8 编码的 `.py` 文件。
2. 保持“DeepSeek 模式”，点击“开始生成”。
3. 查看三个节点的状态，在“文档 / 分析 / 审校 / 消息与日志”之间切换。
4. 下载 Markdown 文档，或导出完整 JSON 运行记录。
5. 如果模型服务暂时失败，解决网络、余额或配置问题后点击“从失败节点恢复”。成功节点不会重复执行。源码语法错误则需要修改源码并新建任务。

端口被占用时使用 `python app.py --port 8766`，再访问对应端口。

## DeepSeek 配置

本机默认从 **`D:\deepseek\api.txt`** 读取密钥。该文件在项目外部，不会复制进源码或提交包。读取优先级是：

1. `DEEPSEEK_API_KEY` 环境变量。
2. `DEEPSEEK_KEY_FILE` 指定的外部文件。
3. 默认路径 `D:\deepseek\api.txt`。

其他电脑可用命令行指定自己的密钥文件：

```powershell
python app.py --key-file "D:\我的配置\api.txt"
```

环境变量配置示例：

```powershell
$env:DEEPSEEK_KEY_FILE = 'D:\deepseek\api.txt'
$env:DEEPSEEK_BASE_URL = 'https://api.deepseek.com'
$env:DEEPSEEK_MODEL = 'deepseek-flash'
python app.py
```

默认模型 `deepseek-flash` 来自开发时核对的 [DeepSeek 官方首次调用文档](https://api-docs.deepseek.com/zh-cn/)；可用 `--model` 或环境变量切换账户可用模型。模型调用按 DeepSeek 的服务规则计费。没有密钥时可选择“离线规则模式”验证完整流程；离线结果由 AST 与规则生成，不冒充模型生成。

**DeepSeek 模式**中：文档 Agent、审校 Agent 各自调用模型，角色提示词和任务目标不同；分析 Agent 使用 AST 提取可靠的静态事实。发送给模型的是函数签名、docstring、调用和异常等分析事实，以及文档草稿。密钥仅用于服务鉴权，不出现在界面、日志和导出记录中。

## 项目能力

| 能力 | 实现 |
| --- | --- |
| 三 Agent 协作 | AnalyzerAgent → WriterAgent → ReviewerAgent |
| Agent 通信 | 带发送方、接收方、类型、时间戳、载荷的结构化消息 |
| 状态共享 | WorkflowState 保存节点状态、输出、消息、日志及尝试次数 |
| 顺序编排 | WorkflowEngine 按配置顺序运行节点 |
| 条件分支 / 有界循环 | 审校不通过时返回文档 Agent，最多自动修订一次 |
| 日志与追踪 | 页面实时轮询状态，可导出 JSON |
| 错误恢复 | 每节点原子保存检查点，失败后复用成功节点 |
| 可视化 | 三节点状态图、结果页签、历史任务 |
| 扩展 | 实现统一 Agent 接口并加入编排节点列表 |

单个任务按顺序执行；最多允许四个独立任务同时运行，不实现单个工作流内的并行节点调度。

## 命令行使用

```powershell
python cli.py samples/order_service.py --mode ai --output generated
python cli.py samples/order_service.py --mode offline --output generated-offline
```

输出 `documentation.md` 和 `trace.json`；任务未通过或失败时进程返回非零状态码。草稿可能已经存在，需结合 trace 的 `status` 和审校结果判断是否是通过版本。

## 测试

```powershell
python -m unittest discover -s tests -v
```

自动测试不访问真实 DeepSeek、不消耗 API 额度。模型测试使用替身验证编排逻辑；真实调用记录另存于 `evidence/deepseek-demo/`，具体结果见 [测试报告](docs/TestReport.md)。

## 文件结构

```text
DocFlow/
├── app.py                  本地 HTTP 服务与后台任务管理
├── cli.py                  命令行入口
├── start.bat               Windows 启动入口
├── docflow/
│   ├── agents.py           分析 / 文档 / 审校 Agent
│   ├── llm.py              DeepSeek 调用与外部密钥读取
│   ├── models.py           工作流状态、消息、结果结构
│   ├── workflow.py         编排、反馈修订、恢复
│   └── store.py            原子 JSON 持久化
├── static/                 中文操作界面
├── samples/                可运行的订单计算示例
├── tests/                  工作流与 HTTP 接口测试
├── data/runs/              本机运行状态（提交包不携带个人运行数据）
├── evidence/               示例文档、运行证据、界面截图
├── docs/                   测试报告、演示稿、课程要求对应表
└── Design.md               架构、流程图、状态与扩展说明
```

## 提交与演示

提交源码压缩包即可；包内已有 README、Design、测试说明和真实 DeepSeek 示例。课程要求压缩包小于 200 MB，并按“学号姓名”命名，因此提交前请把包名改为自己的学号姓名。截图中的截止时间是 **2026 年 10 月 25 日 24 点**。没有替用户提交到课程平台，也没有创建远程仓库。

可按 [一分钟演示稿](docs/Demo.md) 演示。设计说明见 [Design.md](Design.md)，课程要求对应见 [Requirements.md](docs/Requirements.md)。

## 适用范围

本版分析单个 Python 文件，不执行输入源码。分析覆盖顶层函数、类、直接方法、导入、顶层大写常量、签名、docstring、静态调用和显式异常；不分析继承后的完整成员集合、动态行为和嵌套定义。审校检查来源、章节、签名覆盖，并由 DeepSeek 补充语义审查；模型输出仍应人工确认，不保证百分之百正确。

运行历史保存在本机 JSON 文件中，刷新或重启后仍可查看。当前是本地课程 MVP，绑定 127.0.0.1，没有登录与多租户机制。
