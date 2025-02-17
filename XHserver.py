from XingHeFarmworkNew import LLMTask, LLMTools, Inference
from threading import Thread, Lock
from queue import Queue
import os, yaml, importlib, time, logging
from flask import Flask, request, jsonify
import pickle

# 设置日志记录
log_file = 'server_log.log'
with open(log_file, 'w') as file:
        file.truncate(0)
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler(log_file,
                    encoding='utf-8')])
# 创建独立的日志记录器
logger = logging.getLogger('server_log')

# 初始化推理器
ollama = Inference(base_url='http://localhost:11434/v1', api_key='ollama')

class XingHe:
    def __init__(self):
        """
        初始化XingHe类，设置任务模板和任务列表
        """
        self.meta_tasks = []
        self.tasks_list = []
        self.task_templates = self.TaskTemplate()
        self.meta_tasks_lock = Lock()
        self.tasks_list_lock = Lock()
        self.scheduler = None
        logger.info("XingHe 初始化完成")

    class TaskTemplate:
        def __init__(self):
            """
            初始化任务模板类，读取tasks.yaml文件中的任务模板
            """
            with open('tasks.yaml', 'r', encoding='utf-8') as file:
                self.templates = yaml.safe_load(file)["tasks"]
            logger.info("读取到的模板: %s", self.templates)

        def get_template(self, task_name: str):
            """
            根据任务名称获取任务模板
            :param task_name: 任务名称
            :return: 任务模板字典
            """
            for template in self.templates:
                if template["name"] == task_name:
                    return template
            return None
        
        def get_task(self, task_name: str) -> LLMTask:
            """
            根据任务名称获取任务实例
            :param task_name: 任务名称
            :return: LLMTask实例
            """
            template = self.get_template(task_name)
            if template is None:
                logger.error(f"任务 {task_name} 不存在")
                raise ValueError(f"任务 {task_name} 不存在")
            logger.info("匹配到的模板: %s", template)

            llmtools = LLMTools()
            tools_folder = 'Tools'
            if template['tools']:
                self._load_tools(template, llmtools, tools_folder)
            logger.info(f"工具json: {llmtools.tools}, 映射表: {llmtools.available_functions}")
            return LLMTask(template["name"], template["pirority"], template["sysprompt"], llmtools)

        def _load_tools(self, template, llmtools: LLMTools, tools_folder: str):
            """
            加载并匹配工具
            :param template: 任务模板
            :param llmtools: LLMTools实例
            :param tools_folder: 工具文件夹路径
            """
            for tool_file in os.listdir(tools_folder):
                if tool_file.endswith('.py'):
                    tool_name = tool_file[:-3]
                    module = importlib.import_module(f'{tools_folder}.{tool_name}')
                    tool_class = getattr(module, tool_name)
                    if self._is_tool_in_template(tool_class, template):
                        logger.info(f"工具 {tool_class.__name__} 在模板中，激活")
                        llmtools.add_tools([tool_class])

        def _is_tool_in_template(self, tool_class, template):
            """
            检查工具是否在模板中
            :param tool_class: 工具类
            :param template: 任务模板
            :return: 布尔值，表示工具是否在模板中
            """
            for tool_template in template['tools']:
                if list(tool_template.keys())[0] == tool_class.__name__:
                    return True
            return False

    class RestServer:
        def __init__(self, meta_tasks: list, task_templates, tasks_list: list, meta_tasks_lock, tasks_list_lock, port=5000):
            """
            初始化REST服务器类
            :param meta_tasks: 元任务列表
            :param task_templates: 任务模板实例
            :param tasks_list: 任务列表
            :param port: 服务器端口号
            """
            self.app = Flask(__name__)
            self.port = port
            self.meta_tasks = meta_tasks
            self.task_templates = task_templates
            self.tasks_list = tasks_list
            self.meta_tasks_lock = meta_tasks_lock
            self.tasks_list_lock = tasks_list_lock
            self.setup_routes()
            logger.info("REST服务器初始化完成，端口号: %d", self.port)

        def get_system_status(self):
            """
            提取系统运行状态
            :return: 包含系统状态信息的字典
            """
            status = {
            "task_templates": self.task_templates.templates,
            "meta_tasks": [],
            "tasks_list": []
            }

            with self.meta_tasks_lock:
                for task in self.meta_tasks:
                    status["meta_tasks"].append({
                    "uuid": task.info["uuid"],
                    "name": task.info["task_name"],
                    "status": task.status
                    })

            with self.tasks_list_lock:
                for task in self.tasks_list:
                    status["tasks_list"].append({
                    "uuid": task.info["uuid"],
                    "name": task.info["task_name"],
                    "status": task.status
                    })

            return status

        def save_meta_tasks(self, filename='meta_tasks.pkl'):
            """
            保存当前meta_task元任务的状态到本地文件
            :param filename: 保存文件名
            """
            with self.meta_tasks_lock:
                meta_tasks_state = [{'uuid': task.info['uuid'], 'context_ctrl': task.context_ctrl} for task in self.meta_tasks]
                with open(filename, 'wb') as file:
                    pickle.dump(meta_tasks_state, file)
            logger.info("元任务状态已保存到 %s", filename)

        def load_meta_tasks(self, filename='meta_tasks.pkl'):
            """
            从本地文件恢复所有元任务
            :param filename: 恢复文件名
            """
            with open(filename, 'rb') as file:
                meta_tasks_state = pickle.load(file)
            with self.meta_tasks_lock:
                for state in meta_tasks_state:
                    for task in self.meta_tasks:
                        if task.info['uuid'] == state['uuid']:
                            task.context_ctrl = state['context_ctrl']
                            break
            logger.info("元任务状态已从 %s 恢复", filename)

        def setup_routes(self):
            """
            设置REST API路由
            """
            @self.app.route('/activate_task', methods=['POST'])
            def activate_task():
                message = request.json
                self.active_task(message)
                return jsonify({"status": "OK"})

            @self.app.route('/status', methods=['GET'])
            def status():
                logger.info(self.get_system_status())
                return jsonify(self.get_system_status())

            @self.app.route('/save_meta_tasks', methods=['POST'])
            def save_meta_tasks():
                self.save_meta_tasks()
                return jsonify({"status": "OK"})

            @self.app.route('/load_meta_tasks', methods=['POST'])
            def load_meta_tasks():
                self.load_meta_tasks()
                return jsonify({"status": "OK"})

        def active_task(self, message: dict):
            """
            激活任务
            :param message: 包含任务信息的字典
            """
            # 消息的格式为{"name": "task_name", "input": "input", (可选)"parent_uuid": "uuid"}
            if self.task_templates.get_template(message["name"]) == None:
                logger.error(f"任务 {message['name']} 不存在")
                return
            task_info = self.task_templates.get_template(message["name"])

            if task_info["is_meta"]: # 如果是元任务
                new_meta_task = None
                for meta_task in self.meta_tasks:
                    if meta_task.info["task_name"] == message["name"]:
                        if meta_task.status == "Free":
                            new_meta_task = meta_task
                            break
                        elif meta_task.status == "ReUser" or meta_task.status == "ToolCall" or (meta_task.status == "ReTool" and not meta_task.events["suspend"].is_set()):
                            logger.info(f"元任务 {message['name']} 正在运行，等待")
                            return
                        elif meta_task.status == "Ready":
                            logger.error(f"元任务 {message['name']} 已完成，不可重复激活")
                            return
                        elif meta_task.status == "ReTool" and meta_task.events["suspend"].is_set():
                            # 放弃调用工具，返回预设打断模板+用户输入
                            # 递归深入子任务和子任务的子任务直到最后一层，然后从task_list中删除他们
                            self._remove_subtasks(meta_task.info["uuid"])
                            meta_task.suspend("None", "None", False, True, message["input"])
                            return
                        else:
                            logger.error(f"元任务 {message['name']} 状态异常")
                            return
                if new_meta_task is None: # 如果已实例化的元任务列表中没有这个元任务
                    logger.info(f"任务 {message['name']} 是元任务，但未在元任务列表中，创建")
                    # 创建元任务，搞一个统一的创建任务的函数
                    new_meta_task = self.task_templates.get_task(message["name"])
                    with self.meta_tasks_lock:
                        self.meta_tasks.append(new_meta_task) # 添加到元任务列表

                # 激活并放入队列
                new_meta_task.context_ctrl["input"] = message["input"]
                new_meta_task.forward()
                with self.tasks_list_lock:
                    self.tasks_list.append(new_meta_task)
                logger.info(f"元任务 {message['name']} 已激活并添加到任务列表")
                logger.info("当前元任务列表: %s", self.meta_tasks)
            elif message.get("parent_uuid", None) is None:
                logger.error("子任务%s没有指定父任务",message["name"])
            # 如果是子任务
            else:
                for parent_task in self.tasks_list:
                    if parent_task.info["uuid"] == message.get("parent_uuid", None):
                        # 创建子任务
                        child_task = self.task_templates.get_task(message["name"])
                        parent_task.suspend(child_task.info["uuid"], child_task.info["task_name"], True, False)
                        child_task.info["parent_uuid"] = message.get("parent_uuid", None)
                        child_task.context_ctrl["input"] = message["input"]
                        child_task.forward()
                        with self.tasks_list_lock:
                            self.tasks_list.append(child_task)
                        logger.info(f"子任务 {message['name']} 已激活并添加到任务列表")
                        break

        def _remove_subtasks(self, parent_uuid):
            """
            递归删除子任务和子任务的子任务
            :param parent_uuid: 父任务的UUID
            """
            subtasks_to_remove = [task for task in self.tasks_list if task.info.get("parent_uuid") == parent_uuid]
            for subtask in subtasks_to_remove:
                self._remove_subtasks(subtask.info["uuid"])
                self.tasks_list.remove(subtask)
                logger.info(f"子任务 {subtask.info['task_name']} 已从任务列表中删除")

        def start(self):
            """
            启动REST服务器
            """
            self.app.run(host='0.0.0.0', port=self.port)

    class Scheduler:
        def __init__(self, meta_tasks: list, tasks_list: list, meta_tasks_lock, tasks_list_lock):
            """
            初始化调度器类
            :param meta_tasks: 元任务列表
            :param tasks_list: 任务列表
            """
            self.infer_queue = Queue()
            self.meta_tasks = meta_tasks
            self.tasks_list = tasks_list
            self.meta_tasks_lock = meta_tasks_lock
            self.tasks_list_lock = tasks_list_lock
            logger.info("调度器初始化完成")

        def infer(self):
            """
            执行推理任务
            """
            while True:
                task = self.infer_queue.get()
                logger.info(f"开始推理任务 {task.info['uuid']}")
                task.context_ctrl["response"] = ollama.infer('qwen2.5:7b', task.get_context(), task.tools_ctrl["llmtools"].tools)
                task.forward()
                task.events['running'].clear()
                logger.info(f"推理任务 {task.info['uuid']} 完成")

        def toolcall(self, task):
            """
            执行工具调用任务
            :param task: 任务实例
            """
            task.action_toolcall()
            task.events['running'].clear()
            logger.info(f"工具调用任务 {task.info['uuid']} 完成")

        def run(self):
            """
            运行调度器，定期检查任务状态并执行相应操作
            """
            while True:
                time.sleep(0.5) # 0.5秒检查一次, 降低CPU占用
                infer_wait = None
                with self.tasks_list_lock:
                    for task in self.tasks_list:
                        if(task.events["suspend"].is_set() or task.events["running"].is_set()):
                            continue
                        elif (task.status == "ReUser" or task.status == "ReTool"):
                            # 缓存推理任务直到找到优先级最高的
                            if infer_wait is None:
                                infer_wait = task
                            elif task.info["priority"] < infer_wait.info["priority"]:
                                # 优先级数字越小，优先级越高
                                infer_wait = task
                        elif task.status == "ToolCall":
                            task.events['running'].set()
                            Thread(target=self.toolcall, args=(task,)).start()
                        elif task.status == "Ready":
                            # 调用task.get_reply()会导致task状态转移，只允许调用一次！！！
                            if task.info["parent_uuid"]:
                                logger.info("任务 %s 有父任务", task.info["uuid"])
                                # 从self.tasks_list中找到第一个uuid等于parent_uuid的任务，并将其赋值给parent_task
                                parent_task = [find_task for find_task in self.tasks_list if find_task.info["uuid"] == task.info["parent_uuid"]][0]
                                parent_task.suspend(task.info["uuid"], task.info["task_name"], False, False, task.get_reply())
                                logger.info("父任务tool history%s", parent_task.context_ctrl["tool_history"])
                            else:
                                print(task.get_reply())
                                try: #尚未实现发送消息
                                    self.send_message("task_reply",{task.info["task_name"]: task.get_reply()})
                                except Exception as e:
                                    logger.error(f"发送消息失败: {e}")
                            task.events['end'].set()
                            self.tasks_list.remove(task)
                if infer_wait:
                    infer_wait.events['running'].set()
                    self.infer_queue.put(infer_wait)

    def system_init(self):
        """
        系统初始化
        """
        # 不知道这里要干啥，先放着
        pass

    def run(self):
        """
        启动系统，运行服务器和调度器
        """
        rest_server = self.RestServer(self.meta_tasks, self.task_templates, self.tasks_list, self.meta_tasks_lock, self.tasks_list_lock)
        self.scheduler = self.Scheduler(self.meta_tasks, self.tasks_list, self.meta_tasks_lock, self.tasks_list_lock)
        Thread(target=rest_server.start).start()
        Thread(target=self.scheduler.infer).start()
        Thread(target=self.scheduler.run).start()
        logger.info("系统运行中...")
