from deepagents.middleware.subagents import SubAgent                                                         
from langchain_core.language_models import BaseChatModel                                                     
from weather_tool import get_weather                                                                         
                                                                                                                
                                                                                                                
def create_weather_subagent(model: BaseChatModel) -> SubAgent:                                               
    """Erzeugt die deklarative Spezifikation für den Wetter-Subagenten."""                                   
    return {                                                                                                 
        "name": "weather",                                                                                   
        "description": "This subagent can get weather in cities.",                                           
        "system_prompt": "Use the get_weather tool to get the weather in a city.",                           
        "tools": [get_weather],                                                                              
        "model": model,                                                                                      
        "middleware": [],                                                                                    
    }                                       