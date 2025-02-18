# 星绘LLMFarmwork

星绘是一个基于Python的可扩展对话与任务管理，能够自主调用不同提示词工作区，工作区之间互相分离的多步LLM框架。设计期望能够让LLM在角色扮演时可以处理专业请求，而不污染对话上下文，实现“情感”和“理性”分明。

## ✨ 核心特性

- 🔄 基于状态机的任务生命周期管理
- 🛠 支持动态工具函数注册与调用
- 🌲 任务树结构，支持父子任务通信
- 🚦 优先级任务调度
- 🔌 RESTful API接口
- 📊 Gradio可视化界面
- 💾 元任务状态持久化

## 📂 项目结构

```
Chaos_XingHeLLM/
├─ Tools/          # 工具函数目录
├─ XHserver.py     # Flask服务器
├─ XingHeFarmworkNew.py # 核心框架
├─ gradio_REST.py  # Gradio界面
└─ tasks.yaml      # 任务配置
```

## 🚀 快速开始

项目默认使用本地ollama：qwen2.5 7b服务，可在XHserver.py中更改，支持OpenAI compatible APIs

1. 安装依赖
```bash
pip install -r requirements.txt
```

2. 配置任务(tasks.yaml)
```yaml
tasks:
  - name: "ChatWithUser"
    priority: 3
    sysprompt: "你是一个善于调用函数解决问题的人工智能助手"
    tools:
      - solve_riddles
    is_meta: true
```

3. 启动服务
```bash
ollama serve
python gradio_REST.py
```

## 💡 使用方式

### Gradio界面
访问 `http://localhost:7860`

### REST API
```python
import requests
requests.post('http://127.0.0.1:5000/activate_task', 
             json={"name": "ChatWithUser", "input": "你好"})
```

### API接口
- `POST /activate_task` - 激活任务
- `GET /status` - 获取状态
- `POST /save_meta_tasks` - 保存核心任务
- `POST /load_meta_tasks` - 加载核心任务

## 📝 许可证
MIT

## 🤝 贡献
欢迎提交Issue或Pull Request。
