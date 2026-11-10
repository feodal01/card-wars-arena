// Prime's default Python tool can run arbitrary code. Register only the seat's MCP tools.
import { writeSync } from "node:fs";
import { execFile } from "node:child_process";
import { pathToFileURL } from "node:url";
import { promisify } from "node:util";

const execute = promisify(execFile);
const allowed = ["act", "get_state", "read_rules", "submit_deck"];

async function bridge(...args) {
  const [python, script] = JSON.parse(process.env.CARDWARS_PRIME_BRIDGE);
  const { stdout } = await execute(python, ["-I", script, ...args], {
    timeout: 60000,
    maxBuffer: 4 * 1024 * 1024,
  });
  return JSON.parse(stdout);
}

async function arena(pi) {
  const tools = await bridge();
  if (JSON.stringify(tools.map(tool => tool.name).sort()) !== JSON.stringify(allowed)) {
    throw new Error("Unexpected arena MCP inventory");
  }
  for (const { name, description, inputSchema } of tools) {
    pi.registerTool({
      name, label: name, description, parameters: inputSchema,
      async execute(_id, args) {
        return { content: await bridge(name, JSON.stringify(args)), details: {} };
      },
    });
  }
  pi.on("session_start", async () => {
    pi.setActiveTools(allowed);
    if (process.env.CARDWARS_CHECK_MCP === "1") {
      const available = pi.getActiveTools().sort();
      if (JSON.stringify(available) !== JSON.stringify(allowed)) {
        throw new Error("Unexpected active Prime tools");
      }
      await bridge("read_rules", "{}");
      writeSync(1, JSON.stringify({ type: "arena.ready", tools: available }) + "\n");
    }
  });
}

// An in-process factory keeps model, tools and session inside this seatbelt process.
const [sdk, ...args] = process.argv.slice(2);
const { main } = await import(pathToFileURL(sdk).href);
await main(args, { extensionFactories: [arena] });
