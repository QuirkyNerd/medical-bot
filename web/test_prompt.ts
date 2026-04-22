import { chatWithProvider } from "./lib/providers/index";
import { readFileSync } from "fs";
const env = readFileSync(".env.local", "utf-8");
for (const line of env.split("\n")) {
   if (line.startsWith("GROQ_API_KEY=")) {
       process.env.GROQ_API_KEY = line.split("=")[1].trim();
   }
}async function runTests() {
  const inputs = [
    "I have headache",
    "Symptoms of diabetes",
    "Chest pain causes"
  ];

  for (const input of inputs) {
    console.log(`\n===========================================`);
    console.log(`TESTING INPUT: "${input}"`);
    console.log(`===========================================\n`);
    try {
      const response = await chatWithProvider({
        provider: "groq",
        model: "llama-3.1-8b-instant",
        messages: [{ role: "user", content: input }],
        context: {
          country: "US",
          language: "en",
          emergencyNumber: "911"
        }
      });
      console.log(response);
    } catch (e: any) {
      console.error("ERROR:", e.message);
    }
  }
}

runTests();
