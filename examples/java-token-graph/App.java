import com.openai.client.OpenAIClient;
class App { static final String SYSTEM_PROMPT = """
You are a support assistant. Return only valid JSON.
"""; void run(){ client.generate(SYSTEM_PROMPT, "model"); repository.create(SYSTEM_PROMPT); } }
