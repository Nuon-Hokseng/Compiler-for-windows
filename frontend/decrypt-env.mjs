/**
 * decrypt-env.mjs — Decrypt .env.enc -> .env before Next.js starts.
 *
 * Uses the same SHA-256 + XOR + Base64 scheme as the backend.
 * Called automatically via the "predev" / "prebuild" npm scripts.
 */

import { createHash } from "node:crypto";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

const SECRET_KEY =
  "9cbfcce635d1160bf8fd4143a322ef1c1edebc84749ae1d34bcb167347754406";

const ENC_PATH = resolve(__dirname, ".env.enc");
const ENV_PATH = resolve(__dirname, ".env");

function decrypt() {
  if (!existsSync(ENC_PATH)) {
    console.log(`[decrypt-env] WARNING: ${ENC_PATH} not found — skipping`);
    return;
  }

  const key = createHash("sha256").update(SECRET_KEY).digest(); // 32 bytes
  const encoded = readFileSync(ENC_PATH, "utf-8");
  const decoded = Buffer.from(encoded, "base64");

  const decrypted = Buffer.alloc(decoded.length);
  for (let i = 0; i < decoded.length; i++) {
    decrypted[i] = decoded[i] ^ key[i % key.length];
  }

  writeFileSync(ENV_PATH, decrypted);

  // Report keys (not values)
  const lines = decrypted.toString("utf-8").split("\n");
  const keys = lines
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith("#") && l.includes("="))
    .map((l) => l.split("=", 1)[0].trim());

  console.log(`[decrypt-env] Decrypted ${keys.length} variables:`);
  keys.forEach((k) => console.log(`  - ${k}`));
}

decrypt();
