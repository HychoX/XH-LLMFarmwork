from openai import OpenAI
from threading import Event
import json, random, uuid

class LLMTools:
    def __init__(self):
        self.tools = [] # 函数描述，推理时给推理节点
        self.available_functions = {} # 函数名和函数对象的映射
        self.tool_prompt = {}   # 工具调用时的提示，key是函数名，value是含有至少一个提示的列表

    def add_tools(self, tools):
        # function是函数对象，discription是函数描述，函数名在discription.name中，callprompt是调用函数时LLM被注入的记忆
        for tool in tools:
            self.tools.append(tool.description)
            self.available_functions[tool.description['function']['name']] = tool.function
            self.tool_prompt[tool.description['function']['name']] = tool.prompt

# 这一版task类不再含有推理器，只是用于管理记忆返回记忆
# 其内部的response是由推理器返回的，正确运行取决于外部调用的正确性
class LLMTask:
    STATUS = ['Free', 'ReUser', 'ToolCall', 'ReTool', 'Ready']
    # 使用控制反转(IoC)设计模式
    def __init__(self, task_name:str, priority:int, sysprompt:str, tools: LLMTools):
        # 任务自带的标签信息
        self.info = {
            'task_name': task_name,
            'priority' : priority,
            'uuid': str(uuid.uuid4()).replace('-', ''), # 生成任务的唯一标识
            'child_uuid': None,
            'parent_uuid': None,
            'suspended_toolname': None
        }
        
        # 调度启停信号量
        self.events = {
            #'start': Event(),
            'running': Event(),
            'suspend': Event(),
            'end': Event()
        }

        # 记忆结构
        self.context_ctrl = {
            'system_memory': [{'role': 'system', 'content': sysprompt}],
            'user_history': [],
            'tool_history': [],
            'input': None,
            'response': None
        }

        # 工具调用
        self.tools_ctrl = {
            'llmtools': tools,
            'tools_filtered': tools,
            'toolcall_queue': [] # 等待调用的工具的队列
        }

        # 状态机
        self.status = 'Free'

    # 挂起/恢复任务，传入子任务的uuid来判断，谁挂起谁释放
    # tool_name是挂起任务的工具名，用于恢复时调用, 和子任务名字一样
    def suspend(self, uuid:str, tool_name:str, status:bool, interrupt:bool, result = None):
        if status and self.info['child_uuid'] == None: # 挂起任务
            self.info['child_uuid'] = uuid
            self.events['suspend'].set()
            self.info['suspended_toolname'] = tool_name
        elif not status and not interrupt: # 恢复任务
            if self.info['child_uuid'] != uuid:
                raise ValueError('Child UUID not match')
            else:
                # 构造工具回复message
                print('ChildTask output:', result)
                self.context_ctrl['tool_history'].append({'role': 'tool',
                                        'content': str(result),
                                        'name': self.info['suspended_toolname']})
                self.events['suspend'].clear()
                self.info['child_uuid'] = None
                self.info['suspended_toolname'] = None # 恢复后清空挂起工具名
        elif not status and interrupt: # 中断任务，中断模板是写死的，后期改为宏定义
            print('Interrupt with input, 添加%s', "(打断了你的思考):"+str(result))
            self.context_ctrl['user_history'].append({'role': 'user',
                                                    'content': "(打断了你的思考):"+str(result)})
            self.context_ctrl['tool_history'] = [] # 中断后清空工具历史
            self.status_update('ReUser') # 被输入打断，回到ReUser状态。
            self.events['suspend'].clear()
            self.info['child_uuid'] = None
            self.info['suspended_toolname'] = None # 恢复后清空挂起工具名
    
    # 这是一个未经测试的功能,用于在运行时动态增删llm看到的工具
    # 使用这个功能请将其他函数中对llmtools的操作改为对tools_filtered的操作
    # llmtools是原始的工具列表(读取进来的备份)，tools_filtered是经过过滤的工具列表
    def tool_permission(self, tool_name: str, is_allowed:bool):
        if (is_allowed and 
            tool_name in self.tools_ctrl['llmtools'].available_functions.keys() and
            tool_name not in self.tools_ctrl['tools_filtered'].available_functions.keys()):
            self.tools_ctrl['tools_filtered'].add_tools([(tool_name,
                                            self.tools_ctrl['llmtools'].available_functions[tool_name],
                                            self.tools_ctrl['llmtools'].tool_prompt[tool_name])])
        elif (not is_allowed and
            tool_name in self.tools_ctrl['tools_filtered'].available_functions.keys()):
            self.tools_ctrl['tools_filtered'].available_functions.pop(tool_name)
            self.tools_ctrl['tools_filtered'].tools.remove(self.tools_ctrl['llmtools'].available_functions[tool_name])
            self.tools_ctrl['tools_filtered'].tool_prompt.pop(tool_name)

    # -----------------交互START-----------------
    def set_input(self, user_input:str):
        self.context_ctrl['input'] = user_input

    def get_context(self):
        context = self.context_ctrl['system_memory'] + self.context_ctrl['user_history'] + self.context_ctrl['tool_history']
        formatted_context = [{'role': msg['role'], 'content': msg['content']} for msg in context if isinstance(msg, dict)]
        return formatted_context
    
    def get_reply(self):
        # 由外部调用，用于获取回复
        if self.status == 'Ready':
            self.status_update('Free')
            return self.context_ctrl['response'].choices[0].message.content
        else:
            return 'No reply yet'
    # -----------------交互END-----------------
    
    # -----------------状态机START-----------------
    def status_update(self, new_status):
        if new_status in self.STATUS: # 状态只能是预定义的状态
            self.status = new_status

    def action_free(self):
        if self.context_ctrl['input']:
            self.context_ctrl['user_history'].append({'role': 'user',
                                    'content': self.context_ctrl['input']})
            print('收到input:', self.context_ctrl['input'])
            self.context_ctrl['input'] = None
            self.status_update('ReUser')

    def action_reuser(self):
        if self.context_ctrl['response'].choices[0].message.tool_calls:
                # 如果有函数调用，将所有函数调用加入队列
                for tool_call in self.context_ctrl['response'].choices[0].message.tool_calls:
                    # 这里的function是OpenAI定义的一个字典，包含了由LLM响应的函数的名字和参数
                    self.tools_ctrl['toolcall_queue'].append(tool_call.function)
                self.status_update('ToolCall')
        else:
            self.context_ctrl['user_history'].append({'role': 'assistant',
                                    'content': self.context_ctrl['response'].choices[0].message.content})
            self.status_update('Ready')

    def action_toolcall(self):
        tool = self.tools_ctrl['toolcall_queue'].pop(0)
        function_called = self.tools_ctrl['llmtools'].available_functions.get(tool.name) # tool在这是一个字典，推理节点的响应
        if function_called: # 如果函数在可用函数里面就不是None，这里function_called是一个函数对象
            self.context_ctrl['tool_history'].append({'role': 'assistant',
                                    'content': random.choice(self.tools_ctrl['llmtools'].tool_prompt[tool.name])})
            print('Calling function:', tool.name, 'Arguments:', tool.arguments)

            arguments = json.loads(tool.arguments)
            
            # 匹配输入tool.name和self.tools_ctrl.llmtools全部可用工具中哪一个名字name相同，并返回匹配到的工具类
            find_tool = next((find_tool for find_tool in self.tools_ctrl['llmtools'].tools if find_tool['function']['name'] == tool.name), None)
            print('Find tool:', find_tool)
            if find_tool and not find_tool['is_meta']:
                # 如果是子任务唤起函数，需要传递自己的uuid
                output = function_called(**arguments, uuid=self.info['uuid'])
            else:
                output = function_called(**arguments)
            print('Function output:', output)

            # 构造工具回复message
            self.context_ctrl['tool_history'].append({'role': 'tool',
                                    'content': str(output),
                                    'name': tool.name})
        else:
            print('Function', tool.name, 'NotFound')
            self.context_ctrl['tool_history'].append({'role': 'tool',
                                    'content': "Function not found"})
        if len(self.tools_ctrl['toolcall_queue']) == 0:
            self.status_update('ReTool')

    def action_retool(self):
        if self.context_ctrl['response'].choices[0].message.tool_calls:
            # 如果有函数调用，将所有函数调用加入队列
            for tool_call in self.context_ctrl['response'].choices[0].message.tool_calls:
                # 这里的function是OpenAI定义的一个字典，包含了由LLM响应的函数的名字和参数
                self.tools_ctrl['toolcall_queue'].append(tool_call.function)
        else:
            # 如果没有进一步的函数调用，先更新记忆记录对函数的响应，再清空函数历史以准备以后的新函数调用
            self.context_ctrl['user_history'].append({'role': 'assistant',
                                    'content': self.context_ctrl['response'].choices[0].message.content})
            self.context_ctrl['tool_history'] = []
            self.status_update('Ready')

    def forward(self):
        # 状态机里面的每一步都是对记忆的更改，不涉及外部执行，到阶段了先执行推理或工具再forward离开阶段
        if self.status == 'Free':
            self.action_free()
        elif self.status == 'ReUser':
            self.action_reuser()
        elif self.status == 'ReTool':
            self.action_retool()
        # Ready状态是外部调用的标志，在由外部发起的get_reply里面转移到Free
        return self.get_context() #这个返回不接受也行，只是为了方便调试
    # -----------------状态机END-----------------


# 定义推理类，这个推理不再含于任务类，而是独立由系统调用，有几个模型就实例化几个推理器
class Inference:
    def __init__(self, base_url: str, api_key: str):
        # 初始化OpenAI客户端
        self.client = OpenAI(base_url=base_url, api_key=api_key)

    # 调用LLM推理并返回结果
    def infer(self, model: str, messages: list, tools: list = []):
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools
        )
        return response
