from pydantic_core import to_jsonable_python
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.models.groq import GroqModel
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessagesTypeAdapter  
import os
from dotenv import load_dotenv
import json
load_dotenv()

system_prompt = "You are a helpful Ai assistant, which helps the user to get and summarise latest emails, set event in the calendar, and answer general queries."
model = GroqModel('llama-3.3-70b-versatile', provider=GroqProvider(api_key=os.getenv("GROQ")))
agent = Agent(model, 
              system_prompt=system_prompt)

result1 = agent.run_sync('Tell me a joke.')
print(result1)
history_step_1 = result1.all_messages()
as_python_objects = to_jsonable_python(history_step_1)  
json.dump(as_python_objects, open('history_step_1.json', 'w'), indent=4)
same_history_as_step_1 = ModelMessagesTypeAdapter.validate_python(json.load(open('history_step_1.json', 'r')))

result2 = agent.run_sync(  
    'Tell me a different one.', message_history=same_history_as_step_1
)
print(result2)

