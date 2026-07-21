import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const pages = [
  ["challenge", "../src/app/(main)/challenge/page.tsx", "ChallengeContent"],
  ["leaderboard", "../src/app/(main)/leaderboard/page.tsx", "LeaderboardContent"],
  ["wrong book", "../src/app/(main)/wrong-book/page.tsx", "WrongBookContent"],
  ["wrong-book practice", "../src/app/(main)/wrong-book/practice/page.tsx", "WrongBookPracticeContent"],
];

for (const [label, relativePath, contentComponent] of pages) {
  test(`${label} renders inside exactly one MainLayout`, () => {
    const source = readFileSync(new URL(relativePath, import.meta.url), "utf8");

    assert.match(
      source,
      /import\s+\{\s*MainLayout\s*\}\s+from\s+["']@\/components\/layout\/main-layout["']/,
    );
    assert.equal(source.match(/<MainLayout>/g)?.length, 1);
    assert.equal(source.match(/<\/MainLayout>/g)?.length, 1);
    const layoutStart = source.indexOf("<MainLayout>");
    const content = source.indexOf(`<${contentComponent} />`, layoutStart);
    const layoutEnd = source.indexOf("</MainLayout>", content);
    assert.ok(layoutStart >= 0 && content > layoutStart && layoutEnd > content);
  });
}
