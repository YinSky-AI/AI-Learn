/**
 * 内容获取工具 - Mock 数据 & 内容工具函数
 *
 * 功能说明：
 * - 提供固定的 12 门课程 Mock 数据（用于演示和离线场景）
 * - 定义学科、难度、年龄组的常量列表
 * - 为各课程的课时生成 Markdown 内容（专属模板 + 通用模板）
 * - 生成欢迎语、获取星期名称等辅助函数
 * - 课时名称和类型采用固定模板循环分配
 */

import type { Course, Subject, DifficultyLevel, AgeGroup, Lesson, ContentFormat } from "@/types";

/** 学科图标映射（Lucide 图标名称） */
export const SUBJECT_ICONS: Record<Subject, string> = {
  math: "Calculator",
  science: "FlaskConical",
  chinese: "BookOpen",
  english: "Languages",
  programming: "Code2",
  art: "Palette",
  history: "Landmark",
};

/** 学科列表 */
export const SUBJECT_LIST: Array<{ key: Subject; name: string; icon: string }> = [
  { key: "math", name: "数学", icon: "Calculator" },
  { key: "science", name: "科学", icon: "FlaskConical" },
  { key: "chinese", name: "语文", icon: "BookOpen" },
  { key: "english", name: "英语", icon: "Languages" },
  { key: "programming", name: "编程", icon: "Code2" },
  { key: "art", name: "艺术", icon: "Palette" },
  { key: "history", name: "历史", icon: "Landmark" },
];

/** 难度列表 */
export const DIFFICULTY_LIST: Array<{ key: DifficultyLevel; name: string }> = [
  { key: "beginner", name: "入门" },
  { key: "intermediate", name: "进阶" },
  { key: "advanced", name: "高级" },
];

/** 年龄组列表 */
export const AGE_GROUP_LIST: Array<{ key: AgeGroup; name: string }> = [
  { key: "06-09", name: "6-9岁" },
  { key: "10-12", name: "10-12岁" },
  { key: "13-15", name: "13-15岁" },
  { key: "16-18", name: "16-18岁" },
];

/** 固定的 12 门课程数据 */
const FIXED_COURSES: Course[] = [
  {
    id: "course-1",
    title: "趣味数学入门",
    description: "适合6-9岁小朋友的趣味数学入门课程，通过趣味互动的方式学习数学知识。",
    coverImage: "/covers/math-0.jpg",
    subject: "math",
    difficulty: "beginner",
    ageGroup: "06-09",
    duration: 45,
    totalLessons: 12,
    completedLessons: 0,
    progress: 0,
    rating: 4.5,
    enrollCount: 328,
    tags: ["math", "beginner"],
    teacher: { id: "teacher-1", name: "王老师", avatar: "/avatars/teacher-1.jpg" },
    createdAt: "2024-01-01T00:00:00.000Z",
    updatedAt: "2024-06-15T00:00:00.000Z",
  },
  {
    id: "course-2",
    title: "探索自然奥秘",
    description: "适合6-9岁小朋友的探索自然奥秘课程，通过趣味互动的方式学习自然知识。",
    coverImage: "/covers/science-1.jpg",
    subject: "science",
    difficulty: "beginner",
    ageGroup: "06-09",
    duration: 38,
    totalLessons: 10,
    completedLessons: 0,
    progress: 0,
    rating: 4.2,
    enrollCount: 256,
    tags: ["science", "beginner"],
    teacher: { id: "teacher-2", name: "李老师", avatar: "/avatars/teacher-2.jpg" },
    createdAt: "2024-01-02T00:00:00.000Z",
    updatedAt: "2024-06-16T00:00:00.000Z",
  },
  {
    id: "course-3",
    title: "阅读理解技巧",
    description: "适合10-12岁小朋友的阅读理解技巧课程，通过趣味互动的方式学习阅读知识。",
    coverImage: "/covers/chinese-2.jpg",
    subject: "chinese",
    difficulty: "intermediate",
    ageGroup: "10-12",
    duration: 62,
    totalLessons: 14,
    completedLessons: 0,
    progress: 0,
    rating: 4.7,
    enrollCount: 412,
    tags: ["chinese", "intermediate"],
    teacher: { id: "teacher-3", name: "张老师", avatar: "/avatars/teacher-3.jpg" },
    createdAt: "2024-01-03T00:00:00.000Z",
    updatedAt: "2024-06-17T00:00:00.000Z",
  },
  {
    id: "course-4",
    title: "英语自然拼读",
    description: "适合6-9岁小朋友的英语自然拼读课程，通过趣味互动的方式学习英语知识。",
    coverImage: "/covers/english-3.jpg",
    subject: "english",
    difficulty: "beginner",
    ageGroup: "06-09",
    duration: 35,
    totalLessons: 10,
    completedLessons: 0,
    progress: 0,
    rating: 4.3,
    enrollCount: 189,
    tags: ["english", "beginner"],
    teacher: { id: "teacher-4", name: "陈老师", avatar: "/avatars/teacher-4.jpg" },
    createdAt: "2024-01-04T00:00:00.000Z",
    updatedAt: "2024-06-18T00:00:00.000Z",
  },
  {
    id: "course-5",
    title: "Scratch编程启蒙",
    description: "适合6-9岁小朋友的Scratch编程启蒙课程，通过趣味互动的方式学习编程知识。",
    coverImage: "/covers/programming-4.jpg",
    subject: "programming",
    difficulty: "beginner",
    ageGroup: "06-09",
    duration: 78,
    totalLessons: 16,
    completedLessons: 0,
    progress: 0,
    rating: 4.8,
    enrollCount: 567,
    tags: ["programming", "beginner"],
    teacher: { id: "teacher-5", name: "刘老师", avatar: "/avatars/teacher-5.jpg" },
    createdAt: "2024-01-05T00:00:00.000Z",
    updatedAt: "2024-06-19T00:00:00.000Z",
  },
  {
    id: "course-6",
    title: "创意绘画课",
    description: "适合6-9岁小朋友的创意绘画课课程，通过趣味互动的方式学习绘画知识。",
    coverImage: "/covers/art-5.jpg",
    subject: "art",
    difficulty: "beginner",
    ageGroup: "06-09",
    duration: 52,
    totalLessons: 12,
    completedLessons: 0,
    progress: 0,
    rating: 4.1,
    enrollCount: 145,
    tags: ["art", "beginner"],
    teacher: { id: "teacher-1", name: "王老师", avatar: "/avatars/teacher-1.jpg" },
    createdAt: "2024-01-06T00:00:00.000Z",
    updatedAt: "2024-06-20T00:00:00.000Z",
  },
  {
    id: "course-7",
    title: "中华上下五千年",
    description: "适合10-12岁小朋友的中华上下五千年课程，通过趣味互动的方式学习历史知识。",
    coverImage: "/covers/history-6.jpg",
    subject: "history",
    difficulty: "intermediate",
    ageGroup: "10-12",
    duration: 95,
    totalLessons: 20,
    completedLessons: 0,
    progress: 0,
    rating: 4.6,
    enrollCount: 378,
    tags: ["history", "intermediate"],
    teacher: { id: "teacher-2", name: "李老师", avatar: "/avatars/teacher-2.jpg" },
    createdAt: "2024-01-07T00:00:00.000Z",
    updatedAt: "2024-06-21T00:00:00.000Z",
  },
  {
    id: "course-8",
    title: "几何图形世界",
    description: "适合10-12岁小朋友的几何图形世界课程，通过趣味互动的方式学习几何知识。",
    coverImage: "/covers/math-7.jpg",
    subject: "math",
    difficulty: "intermediate",
    ageGroup: "10-12",
    duration: 68,
    totalLessons: 14,
    completedLessons: 0,
    progress: 0,
    rating: 4.4,
    enrollCount: 234,
    tags: ["math", "intermediate"],
    teacher: { id: "teacher-3", name: "张老师", avatar: "/avatars/teacher-3.jpg" },
    createdAt: "2024-01-08T00:00:00.000Z",
    updatedAt: "2024-06-22T00:00:00.000Z",
  },
  {
    id: "course-9",
    title: "物理趣味实验",
    description: "适合13-15岁小朋友的物理趣味实验课程，通过趣味互动的方式学习物理知识。",
    coverImage: "/covers/science-8.jpg",
    subject: "science",
    difficulty: "intermediate",
    ageGroup: "13-15",
    duration: 72,
    totalLessons: 12,
    completedLessons: 0,
    progress: 0,
    rating: 4.5,
    enrollCount: 198,
    tags: ["science", "intermediate"],
    teacher: { id: "teacher-4", name: "陈老师", avatar: "/avatars/teacher-4.jpg" },
    createdAt: "2024-01-09T00:00:00.000Z",
    updatedAt: "2024-06-23T00:00:00.000Z",
  },
  {
    id: "course-10",
    title: "日常口语对话",
    description: "适合10-12岁小朋友的日常口语对话课程，通过趣味互动的方式学习英语知识。",
    coverImage: "/covers/english-9.jpg",
    subject: "english",
    difficulty: "intermediate",
    ageGroup: "10-12",
    duration: 58,
    totalLessons: 16,
    completedLessons: 0,
    progress: 0,
    rating: 4.3,
    enrollCount: 312,
    tags: ["english", "intermediate"],
    teacher: { id: "teacher-5", name: "刘老师", avatar: "/avatars/teacher-5.jpg" },
    createdAt: "2024-01-10T00:00:00.000Z",
    updatedAt: "2024-06-24T00:00:00.000Z",
  },
  {
    id: "course-11",
    title: "Python入门之旅",
    description: "适合13-15岁小朋友的Python入门之旅课程，通过趣味互动的方式学习编程知识。",
    coverImage: "/covers/programming-10.jpg",
    subject: "programming",
    difficulty: "intermediate",
    ageGroup: "13-15",
    duration: 88,
    totalLessons: 18,
    completedLessons: 0,
    progress: 0,
    rating: 4.9,
    enrollCount: 623,
    tags: ["programming", "intermediate"],
    teacher: { id: "teacher-1", name: "王老师", avatar: "/avatars/teacher-1.jpg" },
    createdAt: "2024-01-11T00:00:00.000Z",
    updatedAt: "2024-06-25T00:00:00.000Z",
  },
  {
    id: "course-12",
    title: "写作能力提升",
    description: "适合13-15岁小朋友的写作能力提升课程，通过趣味互动的方式学习写作知识。",
    coverImage: "/covers/chinese-11.jpg",
    subject: "chinese",
    difficulty: "advanced",
    ageGroup: "13-15",
    duration: 74,
    totalLessons: 14,
    completedLessons: 0,
    progress: 0,
    rating: 4.6,
    enrollCount: 267,
    tags: ["chinese", "advanced"],
    teacher: { id: "teacher-2", name: "李老师", avatar: "/avatars/teacher-2.jpg" },
    createdAt: "2024-01-12T00:00:00.000Z",
    updatedAt: "2024-06-26T00:00:00.000Z",
  },
];

/**
 * 生成 Mock 课程数据（固定数据，非随机）
 * @param count - 返回课程数量（默认 12）
 * @returns 课程数组
 */
export function getMockCourses(count: number = 12): Course[] {
  return FIXED_COURSES.slice(0, count);
}

/**
 * 获取固定课程详情
 * @param courseId - 课程 ID
 * @returns 课程对象或 undefined
 */
export function getMockCourseDetail(courseId: string): Course | undefined {
  return FIXED_COURSES.find((c) => c.id === courseId);
}

/**
 * ============================================
 * 课程内容生成 - 为每门课的每个课时生成 Markdown 内容
 * ============================================
 */

/** 课程主题内容模板（按学科和课程 ID 组织） */
const COURSE_CONTENT_TEMPLATES: Record<string, Record<string, Record<string, string>>> = {
  math: {
    "course-1": {
      "课程导学": `## 欢迎来到趣味数学入门！

### 你将学到什么？

在这门课程中，我们将一起探索奇妙的数学世界。数学并不枯燥，它无处不在——从你吃糖果时的分配，到搭积木时的形状，到处都有数学的影子。

### 学习目标

- 认识 **1-100** 以内的数字
- 掌握简单的 **加减法** 运算
- 了解基本的 **图形** 认知
- 培养 **数学思维** 和逻辑能力

> 小贴士：每天学习 15 分钟，坚持一周你就会看到进步！

### 准备工作

请准备好：
1. 铅笔和练习本
2. 一些小物品（如积木、硬币）用于实物计数
3. 好奇心和探索欲！

让我们开始这段有趣的数学之旅吧！`,
      "基础概念": `## 数字的奇妙世界

### 认识数字

数字是我们生活中最常用的工具之一。从数糖果到看时钟，数字无处不在。

**数字 1-10** 是所有数学的基础：

| 数字 | 读法 | 含义 |
|------|------|------|
| 1 | 一 | 单个物体 |
| 2 | 二 | 一双、一对 |
| 3 | 三 | 一组三个 |
| 5 | 五 | 一只手的手指数 |
| 10 | 十 | 两只手的手指总数 |

### 数数的方法

我们可以用很多方法来数数：

- **逐一数数法**：一个一个地数，1、2、3...
- **分组数数法**：两个两个地数，2、4、6...
- **倒着数**：10、9、8...

### 小练习

试一试：数一数你书桌上有几本书？有几个文具？

> 记住：数数的时候，每数一个就做一个标记，这样就不会重复或遗漏了。`,
      "核心知识点": `## 加法的乐趣

### 什么是加法？

**加法**就是把两样东西合在一起，看看一共有多少。加号写作 **"+"**，读作"加"。

例如：3 个苹果 + 2 个苹果 = **5 个苹果**

### 加法口诀

记住这些基本的加法组合，会让你的计算又快又准：

\`\`\`
1 + 1 = 2     2 + 1 = 3     3 + 1 = 4
1 + 2 = 3     2 + 2 = 4     3 + 2 = 5
1 + 3 = 4     2 + 3 = 5     3 + 3 = 6
1 + 4 = 5     2 + 4 = 6     3 + 4 = 7
\`\`\`

### 加法的三个小技巧

1. **交换律**：1 + 2 和 2 + 1 结果一样！
2. **凑十法**：先凑到 10，再加剩下的
3. **数轴法**：在数轴上向右跳

> 重点：**交换律** 是加法最重要的性质之一，两个数交换位置，和不变。`,
      "实例讲解": `## 生活中的加法

### 场景一：买水果

小红有 **5 元钱**，妈妈又给了她 **3 元钱**。小红现在一共有多少钱？

**解答过程：**
- 已知：原有 5 元，又得到 3 元
- 列式：5 + 3 = ?
- 从 5 开始，往右数 3 个数：6、7、8
- **答案：5 + 3 = 8 元**

### 场景二：数动物

农场里有 **4 只小鸡**，又来了 **3 只小鸡**，现在一共有几只？

**解答过程：**
- 画图法：先画 4 个圆圈 ⬤⬤⬤⬤
- 再画 3 个圆圈 ⬤⬤⬤
- 一起数：⬤⬤⬤⬤⬤⬤⬤ = **7 只小鸡**

### 小挑战

小明有 2 支红铅笔和 3 支蓝铅笔，他一共有几支铅笔？

> 提示：不同颜色的铅笔也可以加在一起哦！`,
      "互动练习": `## 加法小闯关

### 第一关：快速口算

请在心中计算以下题目：

1. 2 + 3 = ?
2. 5 + 4 = ?
3. 1 + 6 = ?
4. 7 + 2 = ?
5. 3 + 3 = ?

<details>
<summary>点击查看答案</summary>

1. 2 + 3 = **5**
2. 5 + 4 = **9**
3. 1 + 6 = **7**
4. 7 + 2 = **9**
5. 3 + 3 = **6**

</details>

### 第二关：应用题

**题目**：篮子里有 6 个橘子，爸爸又放进去 4 个，现在篮子里有几个橘子？

<details>
<summary>点击查看解题步骤</summary>

1. 理解题意：求一共有多少个橘子
2. 列出算式：6 + 4 = ?
3. 计算答案：6 + 4 = **10**
4. 答：篮子里有 **10** 个橘子

</details>

### 第三关：找规律

观察下面的数字，找出规律并填空：

2, 4, 6, **?**, 10, **?**

> 提示：每次增加了几？`,
      "知识测验": `## 单元测验：加法基础

### 一、填空题（每题 10 分）

1. 3 + 4 = ___
2. ___ + 2 = 7
3. 5 + ___ = 9
4. 1 + 1 + 1 = ___
5. 6 + 0 = ___

### 二、判断题（每题 10 分）

1. 2 + 3 = 5 （ ）
2. 3 + 4 = 8 （ ）
3. 4 + 4 = 8 （ ）
4. 5 + 2 = 6 （ ）
5. 1 + 0 = 0 （ ）

### 三、应用题（每题 20 分）

**题目**：花园里有 3 朵红花和 5 朵黄花，一共有几朵花？

---

> 完成测验后，请向 AI 助助提交答案，它会帮你批改！`,
      "拓展阅读": `## 数学家的故事：高斯小时候

### 从小就是天才

**卡尔·弗里德里希·高斯**（1777-1855）是德国著名的数学家，被称为"数学王子"。

有趣的是，高斯在 **9 岁的时候**就展现出了惊人的数学天赋。

### 著名的 1+2+3+...+100

有一天，老师让同学们计算：

**1 + 2 + 3 + 4 + ... + 98 + 99 + 100 = ?**

其他同学都在老老实实地一个一个加，而小高斯很快就给出了正确答案：**5050**！

### 他的方法

高斯发现了一个巧妙的方法：

- 第一个数 1 和最后一个数 100 配对：1 + 100 = 101
- 第二个数 2 和倒数第二个数 99 配对：2 + 99 = 101
- 以此类推...每对的和都是 101
- 一共有 100/2 = 50 对
- 所以总和 = 50 × 101 = **5050**

> 思考：如果你遇到类似的题目，能不能也像高斯一样找到巧妙的方法呢？`,
      "综合练习": `## 综合练习：加法大挑战

### 热身题

1. 1 + 1 = ___    2. 2 + 2 = ___    3. 3 + 3 = ___
4. 4 + 1 = ___    5. 5 + 5 = ___    6. 6 + 3 = ___

### 进阶题

7. 3 + 4 + 1 = ___    8. 2 + 2 + 2 = ___    9. 5 + 1 + 3 = ___

### 应用题

**题目一**：小明第一天看了 3 页故事书，第二天看了 4 页，两天一共看了几页？

**题目二**：树上有 2 只小鸟，又飞来了 5 只，现在树上一共有几只小鸟？

**题目三**：妈妈买了 4 个苹果和 3 个香蕉，一共买了几个水果？

---

> 做完所有题目后，可以对照答案检查。全部正确的同学可以获得一颗星！`,
    },
    "course-8": {
      "课程导学": `## 欢迎来到几何图形世界！

### 什么是几何？

**几何学**是研究**形状、大小和空间**的数学分支。你每天都能看到各种几何图形：窗户是长方形、车轮是圆形、路牌是三角形...

### 课程内容

1. 认识基本图形：三角形、正方形、长方形、圆
2. 学习图形的性质和特征
3. 计算图形的**周长**和**面积**
4. 探索图形之间的**关系**

### 准备工具

- 直尺、三角板
- 圆规
- 方格纸

> 几何图形就在我们身边，让我们开始探索吧！`,
      "基础概念": `## 认识基本图形

### 四种基本图形

**1. 三角形**
- 有 **3 条边** 和 **3 个角**
- 三角形是最稳定的图形结构

**2. 正方形**
- 有 **4 条边**，每条边**长度相等**
- 四个角都是**直角**（90度）

**3. 长方形**
- 有 **4 条边**，**对边相等**
- 四个角都是**直角**

**4. 圆**
- 没有直的边，是一条**弯曲的线**
- 每一点到圆心的距离都**相等**

### 对比表格

| 图形 | 边数 | 角数 | 特征 |
|------|------|------|------|
| 三角形 | 3 | 3 | 最稳定的图形 |
| 正方形 | 4 | 4 | 四边等长，四角为直角 |
| 长方形 | 4 | 4 | 对边相等，四角为直角 |
| 圆 | 0 | 0 | 没有直边，完美的曲线 |

> 小知识：蜂巢就是由一个个**正六边形**组成的，这是自然界中最节省材料的结构！`,
      "核心知识点": `## 周长和面积

### 周长

**周长**就是图形**一周的长度**。想象你沿着图形的边缘走一圈，走的距离就是周长。

- **正方形周长** = 边长 × 4
- **长方形周长** = (长 + 宽) × 2
- **圆的周长** = 直径 × π（约等于 3.14）

### 面积

**面积**是图形**占多大地方**，也就是图形内部的大小。

- **正方形面积** = 边长 × 边长 = **S = a²**
- **长方形面积** = 长 × 宽 = **S = a × b**
- **圆的面积** = π × 半径² = **S = πr²**

### 示例

一个长方形花坛，长 **5 米**，宽 **3 米**：

- 周长 = (5 + 3) × 2 = **16 米**
- 面积 = 5 × 3 = **15 平方米**

> 记忆技巧：周长是"绕一圈"的长度，面积是"铺满"的大小。`,
    },
  },
  science: {
    "course-2": {
      "课程导学": `## 欢迎来到探索自然奥秘！

### 大自然的神奇世界

大自然充满了奇妙的现象：为什么天空是蓝色的？为什么树叶会变色？为什么会有四季交替？

在这门课程中，我们将像小科学家一样，通过**观察、实验和思考**来探索这些奥秘。

### 学习内容

- **天气与季节**：了解四季变化的原因
- **植物的秘密**：观察植物的生长过程
- **小动物的世界**：认识常见的小动物
- **水的三种形态**：了解水的奇妙变化

### 学习准备

1. 一个小笔记本，用于记录观察
2. 放大镜
3. 好奇心！

> 科学家最重要的品质就是**好奇心**，保持好奇，大胆提问！`,
      "基础概念": `## 认识我们的地球

### 地球的基本结构

我们生活的地球由几个部分组成：

1. **大气层**：包围地球的空气层
2. **水圈**：地球上的江河湖海
3. **地壳**：地球的固体表面（岩石和土壤）
4. **地幔**：地壳下面的岩浆层
5. **地核**：地球的中心，温度极高

### 地球上有什么？

- **71%** 是海洋
- **29%** 是陆地
- 大气层厚约 **1000 公里**

### 为什么地球适合居住？

1. 适当的**温度**（不太热不太冷）
2. 有充足的**水**
3. 有保护我们的**大气层**
4. 有适合呼吸的**氧气**

      `,
      "核心知识点": `## 植物的生长

### 植物的组成部分

一棵植物主要有以下部分：

**种子** → 发芽 → **根**（吸收水分和养分）→ **茎**（支撑和运输）→ **叶**（光合作用）→ **花** → **果实**

### 光合作用

植物最神奇的能力就是**光合作用**：

> 阳光 + 二氧化碳 + 水 → 氧气 + 养分

植物用**叶绿素**（让叶子变绿的物质）吸收阳光的能量，把二氧化碳和水变成养分，同时释放出氧气。

**公式**：6CO₂ + 6H₂O + 光能 → C₆H₁₂O₆ + 6O₂

### 有趣的事实

- 一棵大树每天可以产生约 **100 升**氧气
- 世界上最高的树可以长到 **115 米**
- 有些植物的种子可以在地下存活几百年`,
    },
    "course-9": {
      "课程导学": `## 欢迎来到物理趣味实验！

### 物理是什么？

**物理学**是研究物质、能量以及它们之间相互作用的科学。从苹果落地到宇宙运行，物理无处不在。

### 实验安全守则

在进行任何实验前，请务必记住：

1. **听从指导**：严格按照步骤操作
2. **注意安全**：远离火源和尖锐物品
3. **保持清洁**：实验后收拾好器材
4. **记录观察**：认真写下你看到的现象

### 本学期实验清单

- 浮力实验：为什么船能浮在水上？
- 光的折射：筷子在水中为什么会"弯"？
- 简单电路：让小灯泡亮起来
- 杠杆原理：怎样用更小的力搬重物？`,
      "基础概念": `## 力与运动

### 什么是力？

**力**就是一个物体对另一个物体的**推**或**拉**。力可以改变物体的运动状态。

### 常见的力

| 力的类型 | 例子 | 说明 |
|---------|------|------|
| 重力 | 苹果落地 | 地球对物体的吸引力 |
| 摩擦力 | 刹车停车 | 接触面之间的阻力 |
| 弹力 | 弹簧拉伸 | 物体恢复原状的力 |
| 浮力 | 船浮在水面 | 流体对物体的向上推力 |

### 牛顿第一定律

> 一个静止的物体保持静止，一个运动的物体保持匀速直线运动，除非受到外力的作用。

这就是为什么：
- 球在地上最终会停下来（摩擦力）
- 冰面上的球会滑很远（摩擦力小）

### 摩擦力的秘密

摩擦力在生活中无处不在：
- 走路靠脚底和地面的**摩擦力**
- 刹车靠刹车片和车轮的**摩擦力**
- 但是摩擦力也会磨损物体

> 思考：如果没有摩擦力，我们的生活会变成什么样？`,
    },
  },
  chinese: {
    "course-3": {
      "课程导学": `## 欢迎来到阅读理解技巧课！

### 为什么要学好阅读理解？

阅读理解是语文学习中最重要的技能之一。好的阅读能力能帮你：

- 更快地**获取信息**
- 更深入地**理解文章**
- 更好地**表达自己**
- 在考试中**取得好成绩**

### 本课程将学习

1. **快速阅读**技巧
2. **段落结构**分析
3. **中心思想**概括
4. **细节信息**提取
5. **推理判断**能力

### 学习方法

> 读书破万卷，下笔如有神。——杜甫

每天坚持阅读 20 分钟，你的阅读能力会稳步提升！`,
      "基础概念": `## 什么是段落？

### 段落的结构

一个好的段落通常包含：

1. **主题句**：表达段落主要意思的句子，通常在段首
2. ** supporting sentences**：用具体事例、数据来支持主题句
3. **结论句**：总结或强调段落的主要观点

### 示例分析

> 春天来了，公园里变得生机勃勃。**柳树抽出嫩绿的新芽**，在微风中轻轻摇摆。**桃花争相开放**，粉红色的花瓣像小姑娘的笑脸。**小燕子从南方飞回来**，在枝头叽叽喳喳地唱歌。**这一切都在告诉我们：春天真美好！**

**分析**：
- 主题句："春天来了，公园里变得生机勃勃"
- 支持句：柳树、桃花、小燕子的描写
- 结论句："春天真美好！"

### 小练习

试着找出下面这段话的主题句：

> 学习需要坚持。每天进步一点点，日积月累就会取得巨大的成就。就像滴水穿石，虽然一滴水的力量很小，但持续不断地滴，终能穿透坚硬的石头。

> 提示：通常主题句出现在段落的开头或结尾。`,
      "核心知识点": `## 如何概括中心思想

### 三步概括法

概括文章的中心思想，可以按照以下三个步骤：

#### 第一步：了解大意

快速通读全文，了解文章**大致讲了什么**。

#### 第二步：分析结构

看看文章分几个部分，每部分讲了什么。

#### 第三步：提炼核心

用 **"谁 + 做了什么 + 结果怎样"** 的句式来概括。

### 实例演示

**文章**：讲述了小马过河的故事。小马要过河，老牛说水很浅可以过，松鼠说水很深很危险。小马回家问妈妈，妈妈让他自己去试试。小马下了河，发现水既不像老牛说的那么浅，也不像松鼠说的那么深。

**概括**：小马在过河时遇到了不同动物的不同意见，经过妈妈鼓励自己去尝试后，发现河水既不太浅也不太深。

### 常见题型

| 题型 | 答题思路 |
|------|---------|
| 概括主要内容 | 谁 + 做了什么 + 结果 |
| 体会作者感情 | 找到抒情、议论的句子 |
| 理解词语含义 | 联系上下文，结合语境 |
| 分析人物特点 | 从言行、心理描写中找依据 |

> 技巧：概括时语言要**简练**，不要照抄原文。`,
    },
    "course-12": {
      "课程导学": `## 欢迎来到写作能力提升课！

### 写作的重要性

写作是表达思想、传递信息的重要方式。好的写作能力不仅对学业有帮助，更能影响你一生的沟通能力。

### 本课程内容

1. **记叙文**写作技巧
2. **描写手法**的运用
3. **议论文**的基本结构
4. **修辞手法**让文章更生动
5. **修改润色**让文章更精彩

### 写作好习惯

> 好文章是改出来的，不是写出来的。

- 多读：积累素材和表达方式
- 多写：每天坚持写日记或随笔
- 多改：写完后多读几遍，反复修改`,
      "基础概念": `## 记叙文的要素

### 六要素

一篇完整的记叙文需要包含**六要素**：

1. **时间**：事情发生的时间
2. **地点**：事情发生的地点
3. **人物**：故事中的人
4. **起因**：为什么发生
5. **经过**：事情的经过
6. **结果**：最终怎样了

### 记叙文的顺序

- **顺叙**：按时间顺序写（最常见）
- **倒叙**：先写结果，再写过程（制造悬念）
- **插叙**：在叙述中插入相关内容

### 开头和结尾

**好的开头**：
- 开门见山：直接点题
- 设问开头：提出问题引发思考
- 场景描写：用环境烘托气氛

**好的结尾**：
- 总结全文，点明主题
- 抒发情感，引起共鸣
- 留下悬念，引人深思

> 开头要引人入胜，结尾要回味无穷。`,
      "核心知识点": `## 描写手法的运用

### 五种感官描写

优秀的写作需要调动读者的**五种感官**：

| 感官 | 描写角度 | 示例 |
|------|---------|------|
| 视觉 | 颜色、形状、光线 | 红彤彤的夕阳 |
| 听觉 | 声音 | 叽叽喳喳的鸟鸣 |
| 嗅觉 | 气味 | 芬芳的花香 |
| 味觉 | 味道 | 甜丝丝的蜂蜜 |
| 触觉 | 温度、质感 | 凉丝丝的微风 |

### 修辞手法

**1. 比喻**
> 弯弯的月亮像一条小船。

**2. 拟人**
> 春风抚摸着大地。

**3. 排比**
> 书是灯塔，指引方向；书是钥匙，开启智慧；书是阶梯，通向成功。

**4. 夸张**
> 他的声音大得能把屋顶掀翻。

### 对比示例

**普通写法**：花开了，很漂亮。

**描写写法**：清晨，一朵朵玫瑰在晨露中悄然绽放，娇艳的花瓣如同少女羞红的脸颊，散发着沁人心脾的芬芳，引来一群彩蝶翩翩起舞。

> 记住：好的描写要**具体**、**生动**、**有画面感**。`,
    },
  },
  english: {
    "course-4": {
      "课程导学": `## Welcome to English Phonics!

### What is Phonics?

**Phonics**（自然拼读）是一种通过学习字母和发音之间的关系来帮助阅读和拼写的方法。

### Why Learn Phonics?

掌握自然拼读可以帮助你：

- **独立阅读**陌生单词
- **准确拼写**英语单词
- 提高英语**阅读速度**
- 建立**英语语感**

### Alphabet Review

Let's review the 26 letters of the English alphabet:

| A | B | C | D | E | F | G |
|---|---|---|---|---|---|---|
| a | b | c | d | e | f | g |

| H | I | J | K | L | M | N |
|---|---|---|---|---|---|---|
| h | i | j | k | l | m | n |

> Tip: Practice saying each letter's name and sound every day!`,
      "基础概念": `## Vowel Sounds (元音发音)

### The Five Vowels

英语中有 **5 个元音字母**：

- **A** - /æ/ as in **a**pple (苹果)
- **E** - /ɛ/ as in **e**lephant (大象)
- **I** - /ɪ/ as in **i**guana (鬣蜥)
- **O** - /ɒ/ as in **o**ctopus (章鱼)
- **U** - /ʌ/ as in **u**mbrella (雨伞)

### Long vs Short Vowels

每个元音都有**长音**和**短音**两种发音：

| 元音 | 短音 (Short) | 长音 (Long) | 规则 |
|------|-------------|-------------|------|
| A | /æ/ cat | /eɪ/ cake | silent e |
| E | /ɛ/ bed | /i:/ seed | silent e |
| I | /ɪ/ sit | /aɪ/ kite | silent e |
| O | /ɒ/ hop | /oʊ/ hope | silent e |
| U | /ʌ/ cut | /ju:/ cube | silent e |

### Magic E Rule (神奇E规则)

当单词以 **"元音 + 辅音 + e"** 结尾时，前面的元音发**长音**，最后的 **e 不发音**：

- m**a**d → m**a**k**e** (/eɪ/)
- p**i**n → p**i**p**e** (/aɪ/)
- h**o**p → h**o**p**e** (/oʊ/)

> Practice: Try reading these words: **lake, bike, home, cute, theme**`,
      "核心知识点": `## Consonant Sounds (辅音发音)

### Common Consonant Digraphs (辅音组合)

两个辅音字母组合在一起，发一个新的音：

**sh** - /ʃ/ ship, shop, fish
**ch** - /tʃ/ chair, cheese, lunch
**th** - /θ/ think, three, bath
**wh** - /w/ whale, wheel, white
**ph** - /f/ phone, photo, elephant

### Blending Practice (拼读练习)

让我们把字母的发音拼在一起：

\`\`\`
c - a - t → /k/ - /æ/ - /t/ → cat
d - o - g → /d/ - /ɒ/ - /ɡ/ → dog
s - u - n → /s/ - /ʌ/ - /n/ → sun
\`\`\`

### Word Families (词族)

相同的结尾，不同的开头：

- **-at 家族**: cat, bat, hat, mat, rat, sat
- **-og 家族**: dog, log, fog, jog, hog
- **-ig 家族**: pig, dig, big, fig, wig

> 小技巧：认识一个词族后，你就能读出整个家族的单词！`,
    },
    "course-10": {
      "课程导学": `## Welcome to Daily English Conversation!

### Course Introduction

本课程将帮助你掌握日常生活中最常用的英语对话，让你能够自信地用英语交流。

### Topics We'll Cover

1. **Greetings** (打招呼与问候)
2. **Self-Introduction** (自我介绍)
3. **At School** (在学校)
4. **At Home** (在家里)
5. **Shopping** (购物)
6. **Food & Drinks** (食物与饮品)

### How to Practice

> Practice makes perfect! 每天练习 10 分钟对话。

- 大声朗读对话
- 和伙伴角色扮演
- 录音回听自己的发音`,
      "基础概念": `## Greetings (打招呼)

### Basic Greetings

| English | 中文 | Usage |
|---------|------|-------|
| Hello! | 你好！ | 任何时间 |
| Hi! | 嗨！ | 随意场合 |
| Good morning! | 早上好！ | 上午 |
| Good afternoon! | 下午好！ | 下午 |
| Good evening! | 晚上好！ | 傍晚 |
| How are you? | 你好吗？ | 询问对方 |
| Nice to meet you! | 很高兴认识你！ | 初次见面 |

### Common Responses

**当别人问 "How are you?" 时：**

- I'm fine, thank you. (我很好，谢谢)
- I'm doing well, thanks. (我很好，多谢)
- Not bad. (还不错)
- How about you? (你呢？)

### Practice Dialogue

\`\`\`
A: Hello! My name is Tom. What's your name?
B: Hi Tom! I'm Lily. Nice to meet you!
A: Nice to meet you too, Lily! How are you today?
B: I'm fine, thank you. And you?
A: I'm doing great, thanks!
\`\`\`

> 记住：英语对话中，礼貌用语非常重要！`,
    },
  },
  programming: {
    "course-5": {
      "课程导学": `## 欢迎来到 Scratch 编程启蒙！

### 什么是 Scratch？

**Scratch** 是一种专为青少年设计的**图形化编程工具**，由麻省理工学院（MIT）开发。你不需要写代码文字，只需要像搭积木一样**拖拽积木块**就能创造出动画、游戏和故事！

### 为什么学编程？

- 锻炼**逻辑思维**能力
- 培养**解决问题**的能力
- 激发**创造力**
- 为将来学习更高级的编程语言打基础

### 你将学会

1. 认识 Scratch 界面
2. 让角色**移动和说话**
3. 创建简单的**动画**
4. 制作第一个**小游戏**
5. 理解**循环、条件**等编程概念

### 准备工作

1. 打开 [scratch.mit.edu](https://scratch.mit.edu)
2. 创建一个免费账号
3. 准备好你的创意！

> 编程就像搭积木，把简单的指令组合起来，就能创造出复杂有趣的作品！`,
      "基础概念": `## 认识 Scratch 界面

### 四大区域

Scratch 界面分为 **4 个主要区域**：

**1. 舞台区（Stage）**
- 位于右上角
- 这里是你的作品**展示**的地方
- 可以看到角色的表演效果

**2. 积木区（Block Palette）**
- 位于左侧
- 包含所有可以使用的**编程积木**
- 按颜色和功能分类

**3. 编程区（Coding Area）**
- 位于中间
- 将积木**拖到这里**组成程序
- 积木之间会像拼图一样**自动吸附**

**4. 角色区（Sprite Pane）**
- 位于右下角
- 管理你的**角色**和**背景**
- 可以添加或删除角色

### 积木的颜色含义

| 颜色 | 类别 | 功能 |
|------|------|------|
| 蓝色 | 运动 | 控制角色移动和旋转 |
| 紫色 | 外观 | 改变角色的大小、颜色 |
| 黄色 | 事件 | 程序开始的条件 |
| 橙色 | 控制 | 循环和条件判断 |
| 绿色 | 运算 | 数学计算和比较 |

> 技巧：先想好你要做什么，再选择合适的积木。编程的第一步是**规划**！`,
      "核心知识点": `## 让角色动起来

### 第一个程序

让我们编写第一个程序，让小猫动起来：

**步骤：**
1. 选择蓝色 **"运动"** 积木
2. 拖出 移动 (10) 步 积木到编程区
3. 点击积木，观察小猫的移动

### 常用运动积木

\`\`\`
移动 (10) 步          // 向当前方向移动
右转 ↻ (15) 度       // 顺时针旋转
左转 ↺ (15) 度       // 逆时针旋转
移到 x:(0) y:(0)     // 移动到指定位置
在 (1) 秒内滑行到 x:(0) y:(0)  // 平滑移动
\`\`\`

### 添加重复（循环）

让角色**持续移动**，我们需要使用循环：

1. 从橙色 **"控制"** 类别中拖出 重复执行 积木
2. 将 移动 (10) 步 放在循环**里面**
3. 再加一个 碰到边缘就反弹 积木

这样小猫就会一直移动，碰到边缘自动弹回来！

### 添加事件触发

- 使用 当 🟢 被点击 开始运行
- 使用 当按下 (空格) 键 用键盘控制

> 挑战：试着让小猫画出正方形！提示：重复 4 次"移动100步，右转90度"。`,
    },
    "course-11": {
      "课程导学": `## 欢迎来到 Python 入门之旅！

### 什么是 Python？

**Python** 是世界上最流行的编程语言之一，以**简单易学**和**功能强大**著称。它被广泛用于：

- **网站开发**：Google、YouTube、Instagram 都使用 Python
- **数据分析**：科学家用它处理海量数据
- **人工智能**：ChatGPT 就是基于 Python 开发的
- **游戏开发**：很多游戏使用 Python 编写脚本

### 为什么选择 Python？

- 语法**简洁**，接近自然语言
- **跨平台**，在 Windows/Mac/Linux 都能运行
- 庞大的**第三方库**生态
- 活跃的**社区**支持

### 学习路线

1. **基础语法**：变量、数据类型、运算
2. **流程控制**：条件判断、循环
3. **数据结构**：列表、字典
4. **函数**：代码的组织与复用
5. **项目实战**：制作小游戏、爬虫等

### 环境准备

在开始之前，请确保已安装 Python 3.8 或更高版本。`,
      "基础概念": `## 变量与数据类型

### 什么是变量？

**变量**就像一个"盒子"，用来存放数据。你可以给它起个名字，然后往里面放东西。

\`\`\`python
# 创建变量
name = "小明"        # 字符串（文字）
age = 13             # 整数（整数）
height = 1.65        # 浮点数（小数）
is_student = True    # 布尔值（真/假）
\`\`\`

### 四种基本数据类型

| 类型 | 关键字 | 示例 | 说明 |
|------|--------|------|------|
| 整数 | int | 42, 0, -3 | 没有小数点的数 |
| 浮点数 | float | 3.14, -0.5 | 带小数点的数 |
| 字符串 | str | "Hello" | 文字，用引号包裹 |
| 布尔值 | bool | True, False | 只有真和假两个值 |

### 字符串操作

\`\`\`python
# 字符串拼接
first_name = "小"
last_name = "明"
full_name = first_name + last_name  # "小明"

# 字符串重复
star = "⭐" * 3  # "⭐⭐⭐"

# f-string 格式化
age = 13
print(f"我今年 {age} 岁")  # 我今年 13 岁
\`\`\`

> 注意：Python 对**大小写敏感**，Name 和 name 是两个不同的变量！`,
      "核心知识点": `## 条件判断与循环

### if 条件判断

\`\`\`python
age = 15

if age >= 18:
    print("你已成年")
elif age >= 12:
    print("你是青少年")
else:
    print("你是儿童")
\`\`\`

### for 循环

\`\`\`python
# 遍历列表
fruits = ["苹果", "香蕉", "橘子"]
for fruit in fruits:
    print(f"我喜欢吃{fruit}")

# range 循环
for i in range(5):
    print(i)  # 输出: 0, 1, 2, 3, 4
\`\`\`

### while 循环

\`\`\`python
count = 0
while count < 5:
    print(f"第 {count + 1} 次循环")
    count += 1
\`\`\`

### 循环控制

- **break**：立即退出循环
- **continue**：跳过本次，进入下一次

\`\`\`python
# 找到第一个能被7整除的数
for i in range(1, 100):
    if i % 7 == 0:
        print(f"找到了：{i}")
        break  # 找到后立即停止
\`\`\`

> 练习：用 for 循环计算 1 到 100 的和。答案应该是 5050！`,
    },
  },
  art: {
    "course-6": {
      "课程导学": `## 欢迎来到创意绘画课！

### 绘画的乐趣

绘画是一种表达自我的美妙方式。每个人天生就有创造力，你只需要学会如何释放它。

### 课程内容

1. **线条与形状**：绘画的基础元素
2. **色彩搭配**：理解颜色之间的关系
3. **简单素描**：学习光影和明暗
4. **创意手工**：用不同材料创作
5. **作品欣赏**：学习从名画中汲取灵感

### 准备工具

- 铅笔（HB、2B）
- 橡皮擦
- 彩色铅笔或蜡笔
- 画纸（A4）
- 水彩颜料和画笔

> 艺术没有标准答案，每个人的作品都是独一无二的！`,
      "基础概念": `## 认识线条与形状

### 五种基本线条

1. **直线**：有力、稳定
2. **曲线**：柔和、流动
3. **折线**：有节奏感
4. **波浪线**：活泼、动感
5. **螺旋线**：神秘、有趣

### 基本形状

所有复杂的图形都可以分解为**基本形状**的组合：

- **圆形** → 太阳、苹果、气球
- **三角形** → 山、树、帽子
- **正方形/长方形** → 房子、窗户、书
- **椭圆形** → 脸、鸡蛋、树叶

### 实践练习

试着只用**圆形和三角形**画一只猫：

1. 画一个大圆（猫脸）
2. 画两个三角形（耳朵）
3. 画小圆形（眼睛和鼻子）
4. 加上胡须（直线）和尾巴（曲线）

> 技巧：画画之前先用基本形状**概括**物体的外形，再添加细节。`,
      "核心知识点": `## 色彩的魅力

### 三原色

绘画中有 **3 种基本颜色**（三原色）：

- 🔴 **红色**
- 🔵 **蓝色**
- 🟡 **黄色**

所有其他颜色都可以由这三种颜色混合而成！

### 色彩混合

| 混合 | 结果 |
|------|------|
| 红 + 黄 | 🟠 橙色 |
| 红 + 蓝 | 🟣 紫色 |
| 蓝 + 黄 | 🟢 绿色 |
| 红 + 黄 + 蓝 | 🟤 棕色（近似） |

### 暖色与冷色

**暖色**（给人温暖的感觉）：
- 红色、橙色、黄色
- 适合表现：阳光、火焰、热情

**冷色**（给人凉爽的感觉）：
- 蓝色、绿色、紫色
- 适合表现：天空、海洋、宁静

### 色彩搭配技巧

1. **对比色搭配**：红和绿、蓝和橙（醒目）
2. **邻近色搭配**：红和橙、蓝和紫（和谐）
3. **同类色搭配**：深蓝和浅蓝（层次感）

> 小知识：梵高的《星空》大量使用了蓝色和黄色的对比色搭配！`,
    },
  },
  history: {
    "course-7": {
      "课程导学": `## 欢迎来到中华上下五千年！

### 为什么学历史？

> 以铜为镜，可以正衣冠；以史为镜，可以知兴替。——唐太宗

学习历史能帮助我们：

- 了解**中华文明**的灿烂辉煌
- 从古人的智慧中获得**启发**
- 理解**当下**社会的形成
- 培养正确的**价值观**

### 课程时间线

我们将按时间顺序学习：

1. **远古传说**：盘古开天、女娲补天
2. **夏商周**：青铜时代、甲骨文
3. **秦汉**：统一帝国、丝绸之路
4. **三国两晋南北朝**：群雄割据
5. **隋唐**：盛世辉煌
6. **宋元明清**：从繁荣到近代

> 历史是一面镜子，让我们照见过去，也照亮未来。`,
      "基础概念": `## 远古传说与华夏起源

### 三皇五帝

**三皇**：
- **伏羲**：发明八卦和渔网
- **神农**（炎帝）：尝百草，教民耕种
- **燧人**：钻木取火

**五帝**：
- **黄帝**：华夏族的始祖
- **颛顼**、**帝喾**、**尧**、**舜**

### 黄帝的故事

黄帝被称为**"人文初祖"**。据说他发明了：

- 🏠 房屋建筑
- 🚗 车辆
- 📜 文字（命仓颉创造）
- 🧵 丝绸（妻子嫘祖发明）

### 大禹治水

**大禹**是夏朝的开创者，以**治水**闻名：

> 大禹三过家门而不入

他改"堵"为"疏"，成功治理了洪水，体现了**智慧**和**奉献精神**。

### 时间线

\`\`\`
约公元前3000年 ─── 三皇五帝时代
约公元前2070年 ─── 夏朝建立（中国第一个王朝）
约公元前1600年 ─── 商朝建立
约公元前1046年 ─── 西周建立
\`\`\``,
      "核心知识点": `## 秦始皇统一中国

### 秦朝的建立

**公元前 221 年**，秦王嬴政统一六国，建立了中国历史上第一个**大一统的中央集权王朝**——秦朝。

秦始皇自称**"始皇帝"**，意思是"第一个皇帝"。

### 秦始皇的重大举措

| 措施 | 内容 | 影响 |
|------|------|------|
| 统一文字 | 小篆为标准文字 | 促进了文化交流 |
| 统一度量衡 | 统一长度、容量、重量 | 方便了贸易和税收 |
| 统一货币 | 圆形方孔的铜钱 | 促进了经济发展 |
| 修筑长城 | 连接各国长城 | 抵御北方匈奴入侵 |
| 修建灵渠 | 沟通长江和珠江水系 | 方便了南北交通 |

### 千里长城

秦长城西起**临洮**（今甘肃），东至**辽东**（今辽宁），全长超过 **5000 公里**。

> 万里长城不仅是伟大的建筑工程，更是中华民族坚韧不屈精神的象征。

### 秦朝的灭亡

秦朝虽然伟大，但因为：
- **赋税沉重**，百姓困苦
- **法律严苛**，刑罚残酷
- **焚书坑儒**，压制思想

仅仅存在了 **15 年** 就灭亡了。这告诉我们：治理国家必须**以民为本**。`,
    },
  },
};

/** 通用课时内容模板（用于未配置专属内容的课程） */
const GENERIC_LESSON_CONTENT: Record<string, string> = {
  video: `## 视频学习：{title}

### 学习目标

通过本节视频课程，你将掌握以下内容：

- 理解 **{title}** 的核心概念
- 学会相关的**基本方法**和技巧
- 能够运用所学知识解决实际问题

### 视频要点

请在观看视频时注意以下要点：

1. **认真听讲**：关注老师讲解的重点内容
2. **做好笔记**：记录关键概念和公式
3. **暂停思考**：遇到不理解的地方可以暂停反复观看

### 观看提示

> 建议在安静的环境下观看，保持专注。视频总时长约 **{duration}** 分钟。`,
  text: `## {title}

### 知识讲解

欢迎学习本节内容。{description}

### 核心概念

本节有几个重要的知识点需要掌握：

1. **概念一**：理解基本定义和原理
2. **概念二**：掌握相关的公式和方法
3. **概念三**：学会在实际情况中应用

### 详细说明

每个知识点都需要通过**理解 → 练习 → 应用**三个步骤来真正掌握。

> 学习没有捷径，但正确的方法可以让学习事半功倍。坚持每天练习，你会看到自己的进步！`,
  interactive: `## 互动学习：{title}

### 学习目标

通过互动练习加深对知识的理解。

### 知识回顾

在开始练习之前，让我们先回顾一下相关的知识点：

- 本节课程的核心内容
- 重要的公式和概念
- 常见的应用场景

### 互动任务

请完成以下互动任务：

1. **理解性任务**：阅读并理解给定的材料
2. **操作性任务**：按照提示完成操作练习
3. **应用性任务**：将所学知识应用到实际场景中

### 小贴士

> 遇到困难不要着急，尝试从不同角度思考问题。如果实在无法解决，可以向 AI 助助求助！`,
  quiz: `## 知识测验：{title}

### 测验说明

本测验共有 **5 道题**，测试你对本节知识的掌握程度。

### 题目

**一、选择题**

1. 下列哪个选项是正确的？
   - A. 选项A
   - B. 选项B
   - C. 选项C
   - D. 选项D

**二、填空题**

2. 请根据所学知识填写正确答案：_____

**三、判断题**

3. 判断以下说法是否正确。

**四、简答题**

4. 请用自己的话解释这个概念。

**五、应用题**

5. 请将所学知识应用到以下场景中。

### 注意事项

- 请独立完成测验
- 可以回顾前面的课程内容
- 完成后请向 AI 助助提交答案`,
  game: `## 趣味游戏：{title}

### 游戏介绍

通过趣味游戏巩固所学知识，让学习更有趣！

### 游戏规则

1. 根据提示完成挑战
2. 每个关卡对应一个知识点
3. 答对得分，答错可以重试
4. 尝试用最短的时间和最少的错误通关

### 关卡说明

**第一关**：基础知识检测
**第二关**：概念理解应用
**第三关**：综合能力挑战

### 游戏提示

> 游戏的目的是帮助你巩固知识，不要害怕犯错。每次错误都是学习的机会！

祝你游戏愉快！`,
};

/**
 * 获取课时内容
 * 优先使用课程专属内容，其次使用通用模板
 * @param courseId - 课程 ID
 * @param lessonTitle - 课时标题
 * @param lessonType - 课时类型
 * @param duration - 课时时长（分钟）
 * @param description - 课时描述
 * @returns Markdown 内容字符串
 */
export function getLessonContent(courseId: string, lessonTitle: string, lessonType: ContentFormat, duration: number, description: string): string {
  // 查找课程所属学科
  const course = getMockCourseDetail(courseId);
  const subject = course?.subject;

  // 查找专属内容
  if (subject && COURSE_CONTENT_TEMPLATES[subject]?.[courseId]?.[lessonTitle]) {
    return COURSE_CONTENT_TEMPLATES[subject][courseId][lessonTitle];
  }

  // 使用通用模板并替换变量
  const template = GENERIC_LESSON_CONTENT[lessonType] || GENERIC_LESSON_CONTENT.text;
  return template
    .replace(/\{title\}/g, lessonTitle)
    .replace(/\{duration\}/g, String(duration))
    .replace(/\{description\}/g, description);
}

/** 固定的课时名称和类型模板（循环使用） */
const LESSON_TEMPLATES: Array<{ title: string; type: Lesson["type"] }> = [
  { title: "课程导学", type: "video" },
  { title: "基础概念", type: "text" },
  { title: "核心知识点", type: "video" },
  { title: "实例讲解", type: "interactive" },
  { title: "互动练习", type: "interactive" },
  { title: "知识测验", type: "quiz" },
  { title: "拓展阅读", type: "text" },
  { title: "综合练习", type: "quiz" },
  { title: "项目实践", type: "game" },
  { title: "总结回顾", type: "video" },
  { title: "挑战关卡", type: "game" },
  { title: "课程回顾", type: "text" },
  { title: "期末评估", type: "quiz" },
  { title: "进阶挑战", type: "interactive" },
  { title: "趣味游戏", type: "game" },
  { title: "创意任务", type: "interactive" },
];

/**
 * 生成 Mock 课时数据（固定数据，非随机）
 * @param courseId - 课程 ID
 * @returns 课时数组
 */
export function getMockLessons(courseId: string): Lesson[] {
  const course = getMockCourseDetail(courseId);
  const lessonCount = course ? course.totalLessons : 12;

  return Array.from({ length: lessonCount }, (_, i) => {
    const template = LESSON_TEMPLATES[i % LESSON_TEMPLATES.length];
    return {
      id: `lesson-${courseId}-${i + 1}`,
      courseId,
      title: template.title,
      description: `这是${template.title}的学习内容，预计用时${10 + ((i * 3) % 20)}分钟。`,
      order: i + 1,
      type: template.type,
      duration: 10 + ((i * 3) % 20),
      content: getLessonContent(courseId, template.title, template.type, 10 + ((i * 3) % 20), `这是${template.title}的学习内容，预计用时${10 + ((i * 3) % 20)}分钟。`),
      completed: i < (course?.completedLessons || 0),
      resources: [],
    };
  });
}

/**
 * 获取欢迎语（根据当前时间段）
 * @param nickname - 用户昵称
 * @returns 欢迎语字符串
 */
export function getWelcomeMessage(nickname: string): string {
  const hour = new Date().getHours();
  let greeting: string;
  if (hour < 6) greeting = "夜深了";
  else if (hour < 12) greeting = "早上好";
  else if (hour < 14) greeting = "中午好";
  else if (hour < 18) greeting = "下午好";
  else greeting = "晚上好";

  return `${greeting}，${nickname}！今天想学点什么？`;
}

/**
 * 获取星期几的中文名
 * @param date - 日期对象
 * @returns "星期X"
 */
export function getWeekdayName(date: Date): string {
  const days = ["日", "一", "二", "三", "四", "五", "六"];
  return `星期${days[date.getDay()]}`;
}
