import com.openai.Client;
class Service { String systemPrompt = "You are a multilingual support assistant."; void run(){ client.generate(systemPrompt, "model"); } }
