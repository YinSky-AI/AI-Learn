import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const root = path.resolve(import.meta.dirname, "..");
const read = (relativePath) => readFileSync(path.join(root, relativePath), "utf8");

test("PWA manifest provides a standalone Chinese learning application", () => {
  const manifestPath = path.join(root, "public", "manifest.json");
  assert.equal(existsSync(manifestPath), true, "public/manifest.json should exist");

  const manifest = JSON.parse(read("public/manifest.json"));
  assert.equal(manifest.display, "standalone");
  assert.equal(manifest.lang, "zh-CN");
  assert.equal(manifest.icons.length >= 3, true);
});

test("PWA has an install prompt and an offline fallback", () => {
  assert.equal(existsSync(path.join(root, "src/components/pwa/install-prompt.tsx")), true);
  assert.equal(existsSync(path.join(root, "src/app/offline/page.tsx")), true);
  assert.match(read("src/components/pwa/install-prompt.tsx"), /beforeinstallprompt/);
});

test("mobile navigation gives every item a 44px touch target", () => {
  const mobileNavigation = read("src/components/layout/mobile-nav.tsx");
  assert.match(mobileNavigation, /min-h-\[44px\]/);
  assert.match(mobileNavigation, /aria-current/);
});
