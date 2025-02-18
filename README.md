# StarDraw LLM Framework

[中文文档](https://github.com/HychoX/XH-LLMFarmwork/blob/main/README_zh.md)

StarDraw is an extensible Python-based framework for dialogue and task management. It enables autonomous invocation of different prompt workspaces, with each workspace isolated from others, forming a multi-step LLM framework. The design aims to allow LLMs to handle professional requests during role-playing without contaminating the conversational context, achieving a clear separation between "emotion" and "reason."

## ✨ Core Features
- 🔄 Task lifecycle management based on state machines
- 🛠 Support for dynamic tool function registration and invocation
- 🌲 Task tree structure with parent-child task communication
- 🚦 Priority-based task scheduling
- 🔌 RESTful API interface
- 📊 Gradio visualization interface
- 💾 Persistent meta-task states

## 📂 Project Structure
```
Chaos_XingHeLLM/
├─ Tools/          # Tool function directory
├─ XHserver.py     # Flask server
├─ XingHeFarmworkNew.py # Core framework
├─ gradio_REST.py  # Gradio interface
└─ tasks.yaml      # Task configuration
```

## 🚀 Quick Start
The project defaults to using the local ollama: qwen2.5 7b service, which can be changed in `XHserver.py`. It supports OpenAI-compatible APIs.

1. Install dependencies
```bash
pip install -r requirements.txt
```

2. Configure tasks (`tasks.yaml`)
```yaml
tasks:
  - name: "ChatWithUser"
    priority: 3
    sysprompt: "You are an AI assistant skilled at solving problems by invoking functions."
    tools:
      - solve_riddles
    is_meta: true
```

3. Start the service
```bash
ollama serve
python gradio_REST.py
```

## 💡 Usage
### Gradio Interface
Visit `http://localhost:7860`

### REST API
```python
import requests
requests.post('http://127.0.0.1:5000/activate_task', 
             json={"name": "ChatWithUser", "input": "Hello"})
```

### API Endpoints
- `POST /activate_task` - Activate a task
- `GET /status` - Get status
- `POST /save_meta_tasks` - Save core tasks
- `POST /load_meta_tasks` - Load core tasks

## 📝 License
GPLv3

## 🤝 Contribution
Feel free to submit Issues or Pull Requests.
