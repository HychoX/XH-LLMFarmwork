import requests

class solve_riddles:
    description = {
            'type': 'function',
            'function': {
                'name': 'solve_riddles',
                'description': 'An expert who will solve all the riddles',
                'parameters': {
                    'type': 'object',
                    'required': ['question'],
                    'properties': {
                        'question': {'type': 'string', 'description': 'The riddle you want to ask'},
                    },
                },
            },
            'is_meta': False
        }

    prompt = ["我问问专业人士"]

    def function(question: str, uuid: str):
        url = 'http://127.0.0.1:5000/activate_task'
        message_dict = {"name": "solve_riddles", "input": question, "parent_uuid": uuid}
        response = requests.post(url, json=message_dict)
        #print("接收到响应: %s",response)
