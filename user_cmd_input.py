import socket, json

def send_message(name, input_data):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(('127.0.0.1', 12345))
        # 创建要发送的字典
        message_dict = {"name": name, "input": input_data}
        message = json.dumps(message_dict)
        # 发送消息
        client_socket.send(message.encode('utf-8'))
        # 接收响应
        response = client_socket.recv(1024).decode('utf-8')
        response_dict = json.loads(response)
        print(f"接收到响应: {response_dict}")
        client_socket.close()

while True:
        user_input = input('Chat with history: ')
        send_message("ChatWithUser", user_input)
