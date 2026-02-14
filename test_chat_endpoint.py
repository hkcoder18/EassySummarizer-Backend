import requests

def test_chat():
    url = "http://localhost:8000/chat"
    payload = {
        "context": "The capital of France is Paris. It is known for its Eiffel Tower.",
        "question": "What is the capital of France?",
        "history": []
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print("Success!")
        print(f"Answer: {response.json()['answer']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_chat()
