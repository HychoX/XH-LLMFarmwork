class subtract_two_numbers:
    description = {
            'type': 'function',
            'function': {
                'name': 'subtract_two_numbers',
                'description': 'Subtract two numbers',
                'parameters': {
                    'type': 'object',
                    'required': ['a', 'b'],
                    'properties': {
                        'a': {'type': 'integer', 'description': 'The first number'},
                        'b': {'type': 'integer', 'description': 'The second number'},
                    },
                },
            },
            'is_meta': True
        }

    prompt = ["我用计算器算一下"]

    def function(a: int, b: int) -> int:
        """
        Subtract two numbers
        """
        return a - b
