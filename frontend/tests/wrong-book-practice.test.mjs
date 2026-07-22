import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(
  new URL("../src/app/(main)/wrong-book/practice/page.tsx", import.meta.url),
  "utf8",
);

test("wrong-book practice keeps loading separate from the empty state", () => {
  assert.match(source, /const \[loading, setLoading\] = useState\(true\)/);
  assert.match(source, /if \(loading\)/);
  assert.match(source, /正在加载错题/);
});

test("wrong-book practice reads filters through Next search params", () => {
  assert.match(source, /useSearchParams\(\)/);
  assert.match(source, /<Suspense[\s\S]*<WrongBookPracticeContent \/>[\s\S]*<\/Suspense>/);
  assert.doesNotMatch(source, /window\.location\.search/);
});
