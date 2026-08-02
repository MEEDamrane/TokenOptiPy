using OpenAI;
class Service { string SystemPrompt = "You are a multilingual support assistant."; void Run(){ client.ChatAsync(messages: SystemPrompt); } }
