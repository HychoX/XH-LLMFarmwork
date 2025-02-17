from XHserver import XingHe
import gradio as gr
import requests

is_get_system_status = False

def activate_task(task_name, input_text):
    activate_task_url = 'http://127.0.0.1:5000/activate_task'
    task_data = {
        "name": task_name,
        "input": input_text,
        "parent_uuid": ""
    }
    response = requests.post(activate_task_url, json=task_data)
    return response.json()

def get_system_status():
    if not is_get_system_status:
        return {}
    status_url = 'http://127.0.0.1:5000/status'
    response = requests.get(status_url)
    return response.json()

def flag_get_system_status():
    global is_get_system_status
    if not is_get_system_status:
        is_get_system_status = True

def save_meta_tasks():
    save_meta_tasks_url = 'http://127.0.0.1:5000/save_meta_tasks'
    response = requests.post(save_meta_tasks_url)
    return response.json()

def load_meta_tasks():
    load_meta_tasks_url = 'http://127.0.0.1:5000/load_meta_tasks'
    response = requests.post(load_meta_tasks_url)
    return response.json()

with gr.Blocks() as demo:

    gr.Markdown("# 任务激活与系统状态监控")
    
    with gr.Row():
        task_name = gr.Textbox(label="任务名称")
        input_text = gr.Textbox(label="输入文本")
        activate_button = gr.Button("激活任务")
        activate_output = gr.Textbox(label="激活任务响应")
        
        activate_button.click(activate_task, inputs=[task_name, input_text], outputs=activate_output)
    
    with gr.Row():
        status_button = gr.Button("获取系统状态")
        status_textbox = gr.Textbox(value = get_system_status, label = "系统状态", interactive=False, every=0.5)
        
        status_button.click(flag_get_system_status)#点一下之后再开始获取系统状态

    with gr.Row():
        save_button = gr.Button("保存元任务状态")
        save_output = gr.Textbox(label="保存元任务状态响应")
        save_button.click(save_meta_tasks, outputs=save_output)

        load_button = gr.Button("恢复元任务状态")
        load_output = gr.Textbox(label="恢复元任务状态响应")
        load_button.click(load_meta_tasks, outputs=load_output)

if __name__ == '__main__':
    xinghe = XingHe()
    xinghe.system_init()
    xinghe.run()
    demo.launch()