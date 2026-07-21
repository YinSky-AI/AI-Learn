import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const root = path.resolve(import.meta.dirname, "..");
const read = (relativePath) => readFileSync(path.join(root, relativePath), "utf8");

test("knowledge graph page exposes subject switch, details and practice entry", () => {
  const pagePath = path.join(root, "src/app/(main)/knowledge-graph/page.tsx");
  assert.equal(existsSync(pagePath), true, "knowledge graph page should exist");
  const page = read("src/app/(main)/knowledge-graph/page.tsx");
  assert.match(page, /数学/);
  assert.match(page, /语文/);
  assert.match(page, /英语/);
  assert.match(page, /知识点详情/);
  assert.match(page, /练习这个知识点/);
  assert.match(page, /掌握度图例/);
});

test("knowledge graph supports loading, empty and mobile responsive states", () => {
  const page = read("src/app/(main)/knowledge-graph/page.tsx");
  assert.match(page, /正在加载知识图谱/);
  assert.match(page, /还没有学习数据/);
  assert.match(page, /grid-cols-1/);
  assert.match(page, /lg:grid-cols/);
  assert.match(page, /min-h-\[44px\]/);
});

test("API types retain nullable mastery for never-learned nodes", () => {
  const types = read("src/types/api.ts");
  assert.match(types, /interface KnowledgeGraphNode/);
  assert.match(types, /mastery: number \| null/);
  assert.match(types, /practice_href\?: string/);
});

test("learning report provides a discoverable knowledge graph entry", () => {
  const report = read("src/app/(main)/report/page.tsx");
  assert.match(report, /href="\/knowledge-graph"/);
  assert.match(report, />知识图谱</);
});
