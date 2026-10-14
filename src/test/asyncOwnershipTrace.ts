import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

export function ownershipTrace(name: string): string[] {
  const trace = JSON.parse(readFileSync(resolve("formal/traces", `${name}.json`), "utf8"));
  if (trace.generator !== "TLC 1.7.4 counterexample"
      || trace.tlc_sha256 !== "936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88") {
    throw new Error(`Unrecognized TLC trace provenance: ${name}`);
  }
  for (const kind of ["model", "config"]) {
    const hash = createHash("sha256").update(readFileSync(resolve(trace[kind]))).digest("hex");
    if (hash !== trace[`${kind}_sha256`]) throw new Error(`Stale ${kind} trace: ${name}`);
  }
  if (!Array.isArray(trace.events) || trace.events.length === 0
      || !trace.events.every((event: unknown) => typeof event === "string" && event.length > 0)) {
    throw new Error(`Missing TLC events: ${name}`);
  }
  const counterexample = readFileSync(resolve(trace.counterexample));
  if (createHash("sha256").update(counterexample).digest("hex") !== trace.counterexample_sha256) {
    throw new Error(`Corrupt TLC counterexample: ${name}`);
  }
  const events = [...counterexample.toString("utf8").matchAll(/^\/\\ lastEvent = "([^"\n]+)"/gm)]
    .map((match) => match[1]).filter((event) => event !== "init");
  if (JSON.stringify(events) !== JSON.stringify(trace.events)) {
    throw new Error(`Events differ from TLC counterexample: ${name}`);
  }
  return trace.events;
}
