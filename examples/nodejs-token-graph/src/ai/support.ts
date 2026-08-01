import fs from "node:fs";

export const SYSTEM_PROMPT = fs.readFileSync("../prompts/system.txt", "utf8");

export async function support(client: any, question: string, conversationHistory: unknown[]) {
  const userPrompt = `Answer this support question: ${question}`;
  const outputSchema = { answer: "string", confidence: "number" };
  return client.responses.create({
    input: [
      { role: "system", content: SYSTEM_PROMPT },
      { role: "user", content: userPrompt },
      ...conversationHistory,
    ],
    text: { format: outputSchema },
  });
}
