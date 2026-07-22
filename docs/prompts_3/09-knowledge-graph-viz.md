# 09 - 知识图谱可视化 + 掌握状态展示

## 任务目标

做一个知识图谱页面，用树状图展示学科的知识点结构，并且：
- 每个知识点显示掌握程度（颜色深浅）
- 点击知识点可以看到详情和相关题目
- 可以跳转到该知识点的练习

这是一个很有"技术感"的功能，面试/答辩展示效果很好。

## 当前代码状态

### 知识点数据

题库中的每道题有 `knowledge_points` 字段（JSON数组），但没有结构化的知识图谱（知识点之间的层级关系）。

### 行为模型

用户的知识点掌握程度存在 `behavior_model.knowledge_mastery` 中。

## 需要做的改动

### Step 1：定义知识图谱数据结构

因为题库中的知识点是扁平的标签，我们需要手动构建一个层级结构。

新建 `backend/app/data/knowledge_graph.py`：

```python
"""
知识图谱数据

按学科组织的知识点层级结构。
这是静态数据，可以根据题库中的知识点手动整理。

结构示例：
{
  "数学": {
    "name": "数学",
    "children": [
      {
        "name": "数与代数",
        "children": [
          { "name": "整数", "id": "整数" },
          { "name": "分数", "id": "分数" },
          { "name": "小数", "id": "小数" },
        ]
      },
      {
        "name": "几何",
        "children": [
          { "name": "三角形", "id": "三角形" },
          { "name": "长方形", "id": "长方形" },
        ]
      }
    ]
  }
}
"""

# 示例知识图谱（根据题库实际知识点补充）
KNOWLEDGE_GRAPH = {
    "语文": {
        "name": "语文",
        "children": [
            {
                "name": "字词基础",
                "children": [
                    {"name": "拼音", "id": "拼音"},
                    {"name": "汉字", "id": "汉字"},
                    {"name": "词语", "id": "词语"},
                    {"name": "成语", "id": "成语"},
                ],
            },
            {
                "name": "阅读理解",
                "children": [
                    {"name": "记叙文", "id": "记叙文"},
                    {"name": "说明文", "id": "说明文"},
                    {"name": "古诗", "id": "古诗"},
                ],
            },
            {
                "name": "写作",
                "children": [
                    {"name": "句子", "id": "句子"},
                    {"name": "段落", "id": "段落"},
                ],
            },
        ],
    },
    "数学": {
        "name": "数学",
        "children": [
            {
                "name": "数与运算",
                "children": [
                    {"name": "整数", "id": "整数"},
                    {"name": "分数", "id": "分数"},
                    {"name": "小数", "id": "小数"},
                    {"name": "四则运算", "id": "四则运算"},
                ],
            },
            {
                "name": "几何图形",
                "children": [
                    {"name": "三角形", "id": "三角形"},
                    {"name": "长方形", "id": "长方形"},
                    {"name": "正方形", "id": "正方形"},
                    {"name": "圆", "id": "圆"},
                    {"name": "周长与面积", "id": "周长与面积"},
                ],
            },
            {
                "name": "应用题",
                "children": [
                    {"name": "行程问题", "id": "行程问题"},
                    {"name": "工程问题", "id": "工程问题"},
                ],
            },
        ],
    },
    "英语": {
        "name": "英语",
        "children": [
            {
                "name": "词汇",
                "children": [
                    {"name": "单词", "id": "单词"},
                    {"name": "短语", "id": "短语"},
                ],
            },
            {
                "name": "语法",
                "children": [
                    {"name": "时态", "id": "时态"},
                    {"name": "句型", "id": "句型"},
                ],
            },
        ],
    },
    # 更多学科...
}


def get_flat_knowledge_points(subject: str) -> list:
    """获取某个学科的所有知识点（扁平化列表）"""
    if subject not in KNOWLEDGE_GRAPH:
        return []
    
    result = []
    def traverse(node):
        if "id" in node:
            result.append(node["id"])
        if "children" in node:
            for child in node["children"]:
                traverse(child)
    
    traverse(KNOWLEDGE_GRAPH[subject])
    return result


def calculate_node_mastery(node, mastery_map: dict) -> float:
    """
    递归计算节点的掌握程度
    - 叶子节点：直接从mastery_map取
    - 非叶子节点：取子节点的平均值
    """
    if "id" in node:
        return mastery_map.get(node["id"], 0.5)  # 默认50%
    
    if "children" in node:
        child_levels = [
            calculate_node_mastery(child, mastery_map)
            for child in node["children"]
        ]
        if child_levels:
            return sum(child_levels) / len(child_levels)
    
    return 0.5


def enrich_graph_with_mastery(subject: str, mastery_map: dict) -> dict:
    """
    给知识图谱的每个节点加上掌握程度
    
    Returns:
        带有mastery字段的图谱结构
    """
    if subject not in KNOWLEDGE_GRAPH:
        return {}
    
    root = KNOWLEDGE_GRAPH[subject]
    
    def enrich(node):
        result = {"name": node["name"]}
        if "id" in node:
            result["id"] = node["id"]
            result["mastery"] = mastery_map.get(node["id"], None)
            result["is_leaf"] = True
        
        if "children" in node:
            result["children"] = [enrich(child) for child in node["children"]]
            # 非叶子节点的掌握度 = 子节点平均
            child_masteries = [c["mastery"] for c in result["children"] if c.get("mastery") is not None]
            if child_masteries:
                result["mastery"] = sum(child_masteries) / len(child_masteries)
            else:
                result["mastery"] = None
            result["is_leaf"] = False
        
        return result
    
    return enrich(root)
```

> 注意：上面的知识点结构是示例，需要根据题库中实际的知识点来补充。可以先从题库的 `knowledge_points` 字段中提取所有知识点，再分类整理。

### Step 2：知识图谱API

在行为/学习相关API中增加：
- GET /api/v1/knowledge-graph?subject=数学 — 获取某个学科的知识图谱（带掌握程度）

### Step 3：前端知识图谱页面

新建 `frontend/src/app/(main)/knowledge-graph/page.tsx`：

```tsx
"use client";

import { useState, useEffect } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Network, ChevronRight, BookOpen, Target } from "lucide-react";

interface TreeNode {
  name: string;
  id?: string;
  mastery?: number | null;
  is_leaf: boolean;
  children?: TreeNode[];
}

// 根据掌握度返回颜色
function getMasteryColor(mastery: number | null | undefined): string {
  if (mastery === null || mastery === undefined) return "bg-gray-200";
  if (mastery >= 0.8) return "bg-green-500";
  if (mastery >= 0.6) return "bg-green-300";
  if (mastery >= 0.4) return "bg-yellow-400";
  if (mastery >= 0.2) return "bg-orange-400";
  return "bg-red-400";
}

function getMasteryText(mastery: number | null | undefined): string {
  if (mastery === null || mastery === undefined) return "未学习";
  if (mastery >= 0.8) return "精通";
  if (mastery >= 0.6) return "掌握";
  if (mastery >= 0.4) return "一般";
  if (mastery >= 0.2) return "薄弱";
  return "很差";
}

export default function KnowledgeGraphPage() {
  const [subject, setSubject] = useState("数学");
  const [graph, setGraph] = useState<TreeNode | null>(null);
  const [selectedNode, setSelectedNode] = useState<TreeNode | null>(null);

  const subjects = ["语文", "数学", "英语", "物理", "化学", "历史", "地理", "生物"];

  useEffect(() => {
    loadGraph();
  }, [subject]);

  const loadGraph = async () => {
    const res = await fetch(`/api/v1/knowledge-graph?subject=${encodeURIComponent(subject)}`);
    const data = await res.json();
    if (data.code === 0) setGraph(data.data);
  };

  // 递归渲染树节点
  const renderNode = (node: TreeNode, level: number = 0) => {
    const isSelected = selectedNode?.id === node.id;
    const masteryColor = getMasteryColor(node.mastery);

    return (
      <div key={node.name} className="mb-1">
        <div
          className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all hover:bg-gray-50 ${
            isSelected ? "ring-2 ring-blue-400 bg-blue-50" : ""
          }`}
          style={{ marginLeft: level * 20 }}
          onClick={() => setSelectedNode(node)}
        >
          {/* 掌握度指示点 */}
          <div className={`w-3 h-3 rounded-full ${masteryColor} flex-shrink-0`} />
          
          {/* 节点名称 */}
          <span className="text-sm flex-1">{node.name}</span>
          
          {/* 掌握度文本 */}
          <span className="text-xs text-gray-500">
            {node.mastery !== null && node.mastery !== undefined
              ? `${Math.round(node.mastery * 100)}%`
              : "-"}
          </span>
          
          {/* 展开箭头 */}
          {!node.is_leaf && (
            <ChevronRight className="w-4 h-4 text-gray-400" />
          )}
        </div>
        
        {/* 子节点 */}
        {node.children && (
          <div className="ml-2 border-l-2 border-gray-100 pl-2">
            {node.children.map((child) => renderNode(child, level + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="container mx-auto px-4 py-6 max-w-5xl">
      <h1 className="text-2xl font-bold mb-6 flex items-center gap-2">
        <Network className="w-7 h-7" />
        知识图谱
      </h1>

      {/* 学科选择 */}
      <Tabs defaultValue={subject} onValueChange={setSubject} className="mb-6">
        <TabsList className="w-full flex-wrap h-auto">
          {subjects.map((s) => (
            <TabsTrigger key={s} value={s} className="flex-1 min-w-[80px]">
              {s}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <div className="grid md:grid-cols-2 gap-6">
        {/* 左侧：知识树 */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">{subject}知识体系</CardTitle>
          </CardHeader>
          <CardContent>
            {graph ? (
              <div className="space-y-1 max-h-[500px] overflow-y-auto">
                {graph.children?.map((child) => renderNode(child))}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-400">加载中...</div>
            )}
          </CardContent>
        </Card>

        {/* 右侧：节点详情 */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">知识点详情</CardTitle>
          </CardHeader>
          <CardContent>
            {selectedNode ? (
              <div className="space-y-4">
                <div>
                  <h3 className="text-xl font-bold mb-2">{selectedNode.name}</h3>
                  <div className="flex items-center gap-2">
                    <div
                      className={`w-4 h-4 rounded-full ${getMasteryColor(
                        selectedNode.mastery
                      )}`}
                    />
                    <span className="text-gray-600">
                      掌握程度：{getMasteryText(selectedNode.mastery)}
                      {selectedNode.mastery !== null &&
                        selectedNode.mastery !== undefined &&
                        ` (${Math.round(selectedNode.mastery * 100)}%)`}
                    </span>
                  </div>
                </div>

                {selectedNode.is_leaf && (
                  <>
                    <div className="p-4 bg-blue-50 rounded-lg">
                      <h4 className="font-medium text-blue-800 mb-2 flex items-center gap-2">
                        <Target className="w-4 h-4" />
                        学习建议
                      </h4>
                      <p className="text-sm text-blue-700">
                        {selectedNode.mastery !== null && selectedNode.mastery !== undefined
                          ? selectedNode.mastery >= 0.7
                            ? "你已经掌握得不错了，可以挑战更难的题目。"
                            : selectedNode.mastery >= 0.4
                            ? "还需要多练习，建议再做10道相关题目。"
                            : "这个知识点比较薄弱，建议先回到课本复习概念。"
                          : "还没做过相关题目，先来试试吧！"}
                      </p>
                    </div>

                    <Button className="w-full">
                      <BookOpen className="w-4 h-4 mr-2" />
                      练习这个知识点
                    </Button>
                  </>
                )}

                {!selectedNode.is_leaf && selectedNode.children && (
                  <div className="p-4 bg-gray-50 rounded-lg">
                    <h4 className="font-medium text-gray-700 mb-2">包含子知识点</h4>
                    <div className="flex flex-wrap gap-2">
                      {selectedNode.children.map((c) => (
                        <span
                          key={c.name}
                          className={`px-2 py-1 text-xs rounded-full text-white ${getMasteryColor(
                            c.mastery
                          )}`}
                        >
                          {c.name}
                          {c.mastery !== null && c.mastery !== undefined
                            ? ` ${Math.round(c.mastery * 100)}%`
                            : ""}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-12 text-gray-400">
                <Network className="w-12 h-12 mx-auto mb-2 opacity-30" />
                <p>点击左侧节点查看详情</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* 图例 */}
      <div className="mt-6 p-4 bg-gray-50 rounded-xl">
        <h4 className="text-sm font-medium text-gray-700 mb-2">掌握程度图例</h4>
        <div className="flex flex-wrap gap-4">
          {[
            { color: "bg-green-500", text: "精通 (80%+)" },
            { color: "bg-green-300", text: "掌握 (60-80%)" },
            { color: "bg-yellow-400", text: "一般 (40-60%)" },
            { color: "bg-orange-400", text: "薄弱 (20-40%)" },
            { color: "bg-red-400", text: "很差 (0-20%)" },
            { color: "bg-gray-200", text: "未学习" },
          ].map((item) => (
            <div key={item.text} className="flex items-center gap-2">
              <div className={`w-4 h-4 rounded-full ${item.color}`} />
              <span className="text-xs text-gray-600">{item.text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

### Step 4：从题库自动提取知识点（辅助脚本）

写一个小脚本，从题库的 `knowledge_points` 字段中提取所有知识点，方便整理知识图谱：

```python
# scripts/extract_knowledge_points.py
"""
从题库中提取所有知识点
运行：python scripts/extract_knowledge_points.py
"""

import sys
sys.path.insert(0, ".")

import asyncio
from collections import Counter
from sqlalchemy import select, func
from app.core.database import async_session
from app.models.question import Question


async def main():
    async with async_session() as db:
        # 按学科统计
        subjects = ["语文", "数学", "英语", "物理", "化学", "历史", "地理", "生物"]
        
        for subject in subjects:
            result = await db.execute(
                select(Question).where(Question.subject == subject)
            )
            questions = result.scalars().all()
            
            kp_counter = Counter()
            for q in questions:
                if q.knowledge_points:
                    for kp in q.knowledge_points:
                        kp_counter[kp] += 1
            
            print(f"\n=== {subject} ({len(questions)}道题) ===")
            for kp, count in kp_counter.most_common():
                print(f"  {kp}: {count}题")


if __name__ == "__main__":
    asyncio.run(main())
```

### Step 5：导航加入口

在侧边栏/底部导航中加入"知识图谱"入口。

## 文件清单

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新建 | `backend/app/data/knowledge_graph.py` | 知识图谱静态数据 |
| 新增API | 知识图谱接口 | 按学科返回带掌握度的图谱 |
| 新建 | `frontend/src/app/(main)/knowledge-graph/page.tsx` | 知识图谱页面 |
| 新建 | `scripts/extract_knowledge_points.py` | 提取知识点辅助脚本 |
| 修改 | 导航组件 | 加入知识图谱入口 |

## 验收标准

- [ ] 知识图谱页面能展示学科的知识点树
- [ ] 每个节点显示掌握程度（颜色+百分比）
- [ ] 点击节点能看到详情和学习建议
- [ ] 叶子节点有"去练习"按钮
- [ ] 不同学科切换正常
- [ ] 图例说明清晰
- [ ] 移动端能正常显示（横向滚动或折叠）

## 注意事项

1. **知识点结构要手动整理**：这个是最费时间的部分，需要根据题库实际的知识点来分类
2. **先做MVP**：先做2-3个学科的，其他学科后面补
3. **掌握度计算**：父节点的掌握度是子节点的平均值，这个简单但够用
4. **没有数据的时候**：新用户没有掌握度数据，显示灰色"未学习"
5. **树的深度**：不要太深，2-3层就好，太深了用户看着累
6. **后面可以加ECharts**：等基础功能跑通了，可以换成ECharts的树图/力导向图，更酷炫

## 依赖关系

- **前置依赖**：08号（行为建模，有知识点掌握数据）
- **后续依赖**：无
