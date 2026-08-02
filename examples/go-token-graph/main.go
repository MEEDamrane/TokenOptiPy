package main
import "github.com/openai/openai-go"
const systemPrompt = `You are a support assistant. Return only valid JSON.`
func run(){ client.CreateChatCompletion(messages, systemPrompt) }
