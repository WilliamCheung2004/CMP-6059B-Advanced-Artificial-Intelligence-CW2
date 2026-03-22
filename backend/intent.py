import spacy

#spacy.cli.download('en_core_web_sm')
nlp = spacy.load('en_core_web_sm')

#define intents with keywords
INTENTS = {
    'greeting': ['hello', 'hi', 'hey', 'good morning', 'good afternoon'],
    'delay_prediction': ['delay', 'late', 'arrival', 'delayed', 'on time', 'when'],
    'find_ticket': ['ticket', 'travel', 'journey', 'book', 'cheap', 'fare', 'train', 'depart', 'arrive'],
    'goodbye': ['bye', 'goodbye', 'thanks', 'thank you', 'done'],
}

#takes input and returns the detected intent based on keyword matching with lemmatised tokens
def detect_intent(message: str) -> str:
    doc = nlp(message.lower())
    
    #get lemmatised tokens
    tokens = [token.lemma_ for token in doc]
    
    #check each intent's keywords against the tokens
    for intent, keywords in INTENTS.items():
        for keyword in keywords:
            if ' ' in keyword: #multi-word keywords
                if keyword in message.lower():
                    return intent
            else: #single word keyword
                if keyword in tokens:
                    return intent   
    
    return 'unknown'


#pulls useful info like station names, dates and time from a message
def extract_entities(message: str) -> dict:
    doc = nlp(message)
    entities = {}
    
    for ent in doc.ents:
        if ent.label_ == 'GPE':  #GPE = places e.g. Norwich, London
            if 'origin' not in entities:
                entities['origin'] = ent.text
            else:
                entities['destination'] = ent.text
        elif ent.label_ == 'DATE':
            entities['date'] = ent.text
        elif ent.label_ == 'TIME':
            entities['time'] = ent.text
    
    return entities

if __name__ == '__main__':
    tests = [
        "Good morning!",
        "I want to find a cheap ticket from Norwich to London",
        "Can I get a ticket from Norwich to Oxford on the 25th March?",
        "My train is delayed by 10 minutes",
        "Goodbye!",
        "random gibberish blah blah",
        "Will my train arrive on time?"
    ]
    
    for msg in tests:
        intent = detect_intent(msg)
        entities = extract_entities(msg)
        print(f"Message: '{msg}'")
        print(f"  Intent: {intent}")
        print(f"  Entities: {entities}")
        print()