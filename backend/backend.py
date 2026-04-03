from intent import * 
from expertSystem import * 
from datetime import datetime
import numpy as np

talking = False
greeted = False

now = datetime.now()
current_time = now.strftime("%H:%M")

def determine_greeting():
    hour = int(now.strftime("%H"))
    if 6 <= hour < 12:
        return "Good morning, "
    elif 12 <= hour < 18:
        return "Good afternoon,"
    else:
        return "Good evening, "

if __name__ == "__main__":
    while True:
        if talking == False:
            break
    
    #Basic opening greeting 
    if not greeted:
        print(determine_greeting() + " what would you like to do?") 
        greeted = True
    else:    
        print("Hello, what would you like to do?") 
        
    response = input()
        
    correct = correctResponse(response)
    # if(correct != None):
    #     print("Did you mean: " + correct)
    # else:
    #     print("So you want" + response)
        
    
    