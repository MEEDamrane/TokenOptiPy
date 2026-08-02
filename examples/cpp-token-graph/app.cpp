#include "prompt.hpp"
void run() { llama_chat(SYSTEM_PROMPT, "model"); database_create(SYSTEM_PROMPT); }
