use async_openai::Client;
const SYSTEM_PROMPT: &str = r#"You are a support assistant. Return only valid JSON."#;
fn run(){ client.chat(SYSTEM_PROMPT, "model"); }
