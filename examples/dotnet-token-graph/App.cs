using Azure.AI.OpenAI;
class App { const string SystemPrompt = """You are a support assistant. Return only JSON."""; async void Run(){ await client.CompleteChatAsync(messages: SystemPrompt); await http.SendAsync(request); } }
