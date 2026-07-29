from services.llm_service import classify_customer


def handle(client, history, message):
    return classify_customer(client, history, message)
