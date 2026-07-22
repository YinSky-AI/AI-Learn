import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const root = path.resolve(import.meta.dirname, "..");
const read = (relativePath) => readFileSync(path.join(root, relativePath), "utf8");

test("knowledge graph sends the graph node id, name and subject to focused practice", () => {
  const page = read("src/app/(main)/knowledge-graph/page.tsx");
  assert.match(page, /node_id/);
  assert.match(page, /name/);
  assert.match(page, /subject/);
  assert.match(page, /\/knowledge-practice\?/);
});

test("focused practice uses safe questions and the server learning session loop", () => {
  const relativePath = "src/app/(main)/knowledge-practice/page.tsx";
  assert.equal(existsSync(path.join(root, relativePath)), true, "focused practice page should exist");
  const page = read(relativePath);

  assert.match(page, /MainLayout/);
  assert.match(page, /useSearchParams/);
  assert.match(page, /\/v1\/knowledge-graph\/\$\{graphNodeId\}\/practice/);
  assert.match(page, /mapQuizQuestion/);
  assert.match(page, /<QuizPractice/);
  assert.match(page, /knowledgeNodeId=\{practice\.knowledge_node_id\}/);
  assert.match(page, /difficultyLevel=\{practice\.difficulty_level\}/);
  assert.match(page, /正在加载专项练习/);
  assert.match(page, /专项练习暂时无法加载/);
  assert.match(page, /这个知识点暂时没有可练习的题目/);
});
