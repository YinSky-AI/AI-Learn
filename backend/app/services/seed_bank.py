# -*- coding: utf-8 -*-
"""
种子题库与变式生成引擎

管理种子题目模板，并通过参数替换自动生成变式题目。
支持数学、语文、科学等多个学科的题目变式生成。

使用纯 Python 标准库（random, re, json），不引入第三方依赖。
"""

import random
import re
import json
import copy
from typing import Optional


# ============================================================
# 预置种子题库（共 20+ 个种子模板）
# ============================================================
BUILT_IN_SEEDS = [
    # ----------------------------------------------------------
    # 数学 6-8 岁：加法（3 个）
    # ----------------------------------------------------------
    {
        "template_id": "math_6-8_add_001",
        "subject": "math",
        "age_group": "6-8",
        "difficulty": "beginner",
        "type": "single_choice",
        "content_template": "{name}有{a}个苹果，又买了{b}个，现在一共有____个苹果。",
        "variables": {
            "name": ["小明", "小红", "小华", "小丽", "小刚"],
            "a": {"type": "int", "min": 5, "max": 15},
            "b": {"type": "int", "min": 3, "max": 10}
        },
        "answer_formula": "a + b",
        "options_generator": {
            "strategy": "common_mistakes",
            "mistakes": ["a - b", "a * b", "a + b + 1", "a + b - 1"]
        },
        "explanation_template": "用加法计算：{a} + {b} = {answer}。{name}原来有{a}个苹果，又买了{b}个，总数就是{answer}个。",
        "tags": ["加法", "应用题"],
        "knowledge_points": ["20以内加法"],
        "max_variants": 20
    },
    {
        "template_id": "math_6-8_add_002",
        "subject": "math",
        "age_group": "6-8",
        "difficulty": "beginner",
        "type": "single_choice",
        "content_template": "树上原来有{a}只小鸟，又飞来了{b}只，现在树上一共有____只小鸟。",
        "variables": {
            "a": {"type": "int", "min": 4, "max": 12},
            "b": {"type": "int", "min": 3, "max": 8}
        },
        "answer_formula": "a + b",
        "options_generator": {
            "strategy": "common_mistakes",
            "mistakes": ["a - b", "a + b + 2", "a * b", "a + b - 2"]
        },
        "explanation_template": "用加法计算：{a} + {b} = {answer}。原来{a}只，又飞来{b}只，合起来就是{answer}只。",
        "tags": ["加法", "应用题"],
        "knowledge_points": ["20以内加法"],
        "max_variants": 20
    },
    {
        "template_id": "math_6-8_add_003",
        "subject": "math",
        "age_group": "6-8",
        "difficulty": "beginner",
        "type": "single_choice",
        "content_template": "{name}昨天写了{a}个大字，今天写了{b}个大字，两天一共写了____个大字。",
        "variables": {
            "name": ["小芳", "小军", "小梅", "小强", "小玲"],
            "a": {"type": "int", "min": 3, "max": 10},
            "b": {"type": "int", "min": 3, "max": 10}
        },
        "answer_formula": "a + b",
        "options_generator": {
            "strategy": "common_mistakes",
            "mistakes": ["a - b", "a + b + 1", "a * b", "abs(a-b)"]
        },
        "explanation_template": "用加法计算：{a} + {b} = {answer}。把两天写的字数加在一起，就是{answer}个大字。",
        "tags": ["加法", "应用题"],
        "knowledge_points": ["20以内加法"],
        "max_variants": 20
    },

    # ----------------------------------------------------------
    # 数学 6-8 岁：减法（2 个）
    # ----------------------------------------------------------
    {
        "template_id": "math_6-8_sub_001",
        "subject": "math",
        "age_group": "6-8",
        "difficulty": "beginner",
        "type": "single_choice",
        "content_template": "{name}有{a}个苹果，给了{b}个，还剩____个苹果。",
        "variables": {
            "name": ["小明", "小红", "小华", "小丽", "小刚"],
            "a": {"type": "int", "min": 10, "max": 20},
            "b": {"type": "int", "min": 1, "max": 9, "constraint": "b < a"}
        },
        "answer_formula": "a - b",
        "options_generator": {
            "strategy": "common_mistakes",
            "mistakes": ["a+b", "a*b", "a-b+1", "a/b"]
        },
        "explanation_template": "用减法计算：{a} - {b} = {answer}。{name}原来有{a}个苹果，给了{b}个后，剩下的数量就是{answer}个。",
        "tags": ["减法", "应用题"],
        "knowledge_points": ["20以内减法"],
        "max_variants": 20
    },
    {
        "template_id": "math_6-8_sub_002",
        "subject": "math",
        "age_group": "6-8",
        "difficulty": "beginner",
        "type": "single_choice",
        "content_template": "停车场原来有{a}辆车，开走了{b}辆，停车场现在还有____辆车。",
        "variables": {
            "a": {"type": "int", "min": 12, "max": 20},
            "b": {"type": "int", "min": 3, "max": 10, "constraint": "b < a"}
        },
        "answer_formula": "a - b",
        "options_generator": {
            "strategy": "common_mistakes",
            "mistakes": ["a + b", "a - b + 2", "a - b - 1", "a * b"]
        },
        "explanation_template": "用减法计算：{a} - {b} = {answer}。原来{a}辆，开走{b}辆，剩下{answer}辆。",
        "tags": ["减法", "应用题"],
        "knowledge_points": ["20以内减法"],
        "max_variants": 20
    },

    # ----------------------------------------------------------
    # 数学 6-8 岁：几何（2 个）
    # ----------------------------------------------------------
    {
        "template_id": "math_6-8_geo_001",
        "subject": "math",
        "age_group": "6-8",
        "difficulty": "beginner",
        "type": "single_choice",
        "content_template": "一个正方形有{a}条边，那么{b}个正方形一共有____条边。",
        "variables": {
            "a": {"type": "int", "min": 4, "max": 4},
            "b": {"type": "int", "min": 2, "max": 5}
        },
        "answer_formula": "a * b",
        "options_generator": {
            "strategy": "common_mistakes",
            "mistakes": ["a + b", "a + b + 2", "a * b + 1", "a * b - 1"]
        },
        "explanation_template": "每个正方形有{a}条边，{b}个正方形就是 {a} x {b} = {answer} 条边。",
        "tags": ["几何", "正方形"],
        "knowledge_points": ["图形认识", "乘法入门"],
        "max_variants": 20
    },
    {
        "template_id": "math_6-8_geo_002",
        "subject": "math",
        "age_group": "6-8",
        "difficulty": "beginner",
        "type": "single_choice",
        "content_template": "一个三角形有{a}个角，那么{b}个三角形一共有____个角。",
        "variables": {
            "a": {"type": "int", "min": 3, "max": 3},
            "b": {"type": "int", "min": 2, "max": 6}
        },
        "answer_formula": "a * b",
        "options_generator": {
            "strategy": "common_mistakes",
            "mistakes": ["a + b", "a * b + 2", "a * b - 1", "a + b + 1"]
        },
        "explanation_template": "每个三角形有{a}个角，{b}个三角形就是 {a} x {b} = {answer} 个角。",
        "tags": ["几何", "三角形"],
        "knowledge_points": ["图形认识", "乘法入门"],
        "max_variants": 20
    },

    # ----------------------------------------------------------
    # 数学 9-12 岁：分数运算（3 个）
    # ----------------------------------------------------------
    {
        "template_id": "math_9-12_frac_001",
        "subject": "math",
        "age_group": "9-12",
        "difficulty": "intermediate",
        "type": "single_choice",
        "content_template": "计算：{a}/{b} + {c}/{d} = ____（结果化为最简分数）",
        "variables": {
            "a": {"type": "int", "min": 1, "max": 5},
            "b": {"type": "int", "min": 2, "max": 8, "constraint": "a < b"},
            "c": {"type": "int", "min": 1, "max": 5},
            "d": {"type": "int", "min": 2, "max": 8, "constraint": "c < d"}
        },
        "answer_formula": "a*d + b*c, b*d",
        "options_generator": {
            "strategy": "common_mistakes",
            "mistakes": ["a/b + c/d", "a*c/(b*d)", "(a+c)/(b+d)", "(a-c)/(b+d)"]
        },
        "explanation_template": "异分母分数相加：{a}/{b} + {c}/{d} = ({a}x{d} + {c}x{b}) / ({b}x{d}) = {answer_num}/{answer_den}，化为最简分数即可。",
        "tags": ["分数", "加法"],
        "knowledge_points": ["异分母分数加法", "通分"],
        "max_variants": 20
    },
    {
        "template_id": "math_9-12_frac_002",
        "subject": "math",
        "age_group": "9-12",
        "difficulty": "intermediate",
        "type": "single_choice",
        "content_template": "计算：{a}/{b} - {c}/{d} = ____（结果化为最简分数）",
        "variables": {
            "a": {"type": "int", "min": 2, "max": 7},
            "b": {"type": "int", "min": 2, "max": 8, "constraint": "a < b"},
            "c": {"type": "int", "min": 1, "max": 4},
            "d": {"type": "int", "min": 2, "max": 8, "constraint": "c < d"}
        },
        "answer_formula": "a*d - b*c, b*d",
        "options_generator": {
            "strategy": "common_mistakes",
            "mistakes": ["a/b - c/d", "(a-c)/(b-d)", "a*c/(b*d)", "(a+c)/(b+d)"]
        },
        "explanation_template": "异分母分数相减：{a}/{b} - {c}/{d} = ({a}x{d} - {c}x{b}) / ({b}x{d}) = {answer_num}/{answer_den}，化为最简分数即可。",
        "tags": ["分数", "减法"],
        "knowledge_points": ["异分母分数减法", "通分"],
        "max_variants": 20
    },
    {
        "template_id": "math_9-12_frac_003",
        "subject": "math",
        "age_group": "9-12",
        "difficulty": "intermediate",
        "type": "single_choice",
        "content_template": "计算：{a}/{b} x {c}/{d} = ____（结果化为最简分数）",
        "variables": {
            "a": {"type": "int", "min": 1, "max": 5},
            "b": {"type": "int", "min": 2, "max": 6, "constraint": "a < b"},
            "c": {"type": "int", "min": 1, "max": 5},
            "d": {"type": "int", "min": 2, "max": 6, "constraint": "c < d"}
        },
        "answer_formula": "a*c, b*d",
        "options_generator": {
            "strategy": "common_mistakes",
            "mistakes": ["(a+c)/(b+d)", "a/b + c/d", "a*d/(b*c)", "(a*b)/(c*d)"]
        },
        "explanation_template": "分数乘法：{a}/{b} x {c}/{d} = ({a}x{c}) / ({b}x{d}) = {answer_num}/{answer_den}，化为最简分数即可。",
        "tags": ["分数", "乘法"],
        "knowledge_points": ["分数乘法", "约分"],
        "max_variants": 20
    },

    # ----------------------------------------------------------
    # 数学 9-12 岁：方程（2 个）
    # ----------------------------------------------------------
    {
        "template_id": "math_9-12_eq_001",
        "subject": "math",
        "age_group": "9-12",
        "difficulty": "intermediate",
        "type": "single_choice",
        "content_template": "解方程：{a}x + {b} = {c}，x = ____",
        "variables": {
            "a": {"type": "int", "min": 2, "max": 9},
            "b": {"type": "int", "min": 1, "max": 15},
            "c": {"type": "int", "min": 10, "max": 50}
        },
        "answer_formula": "(c - b) / a",
        "options_generator": {
            "strategy": "random_near",
            "mistakes": ["(c + b) / a", "c / a - b", "(c - b) * a"]
        },
        "explanation_template": "方程 {a}x + {b} = {c}，移项得 {a}x = {c} - {b} = {c_minus_b}，所以 x = {c_minus_b} / {a} = {answer}。",
        "tags": ["方程", "一元一次方程"],
        "knowledge_points": ["一元一次方程", "移项"],
        "max_variants": 20
    },
    {
        "template_id": "math_9-12_eq_002",
        "subject": "math",
        "age_group": "9-12",
        "difficulty": "intermediate",
        "type": "single_choice",
        "content_template": "解方程：{a}x - {b} = {c}，x = ____",
        "variables": {
            "a": {"type": "int", "min": 2, "max": 9},
            "b": {"type": "int", "min": 1, "max": 15},
            "c": {"type": "int", "min": 1, "max": 30}
        },
        "answer_formula": "(c + b) / a",
        "options_generator": {
            "strategy": "random_near",
            "mistakes": ["(c - b) / a", "c / a + b", "(c + b) * a"]
        },
        "explanation_template": "方程 {a}x - {b} = {c}，移项得 {a}x = {c} + {b} = {c_plus_b}，所以 x = {c_plus_b} / {a} = {answer}。",
        "tags": ["方程", "一元一次方程"],
        "knowledge_points": ["一元一次方程", "移项"],
        "max_variants": 20
    },

    # ----------------------------------------------------------
    # 语文 6-8 岁：拼音（3 个）
    # ----------------------------------------------------------
    {
        "template_id": "chinese_6-8_pinyin_001",
        "subject": "chinese",
        "age_group": "6-8",
        "difficulty": "beginner",
        "type": "single_choice",
        "content_template": "下列哪个字的拼音正确？",
        "variables": {
            "word": ["花", "草", "鸟", "鱼", "虫"],
            "correct_pinyin": ["huā", "cǎo", "niǎo", "yú", "chóng"]
        },
        "answer_formula": "correct_pinyin",
        "options_generator": {
            "strategy": "common_mistakes",
            "mistakes": []
        },
        "explanation_template": "\"{word}\"的正确拼音是 \"{answer}\"，注意声母和韵母的拼读。",
        "tags": ["拼音", "声母韵母"],
        "knowledge_points": ["汉字拼音认读"],
        "max_variants": 20
    },
    {
        "template_id": "chinese_6-8_pinyin_002",
        "subject": "chinese",
        "age_group": "6-8",
        "difficulty": "beginner",
        "type": "single_choice",
        "content_template": "\"{word}\"的读音是哪一项？",
        "variables": {
            "word": ["山", "水", "日", "月", "风"],
            "correct_pinyin": ["shān", "shuǐ", "rì", "yuè", "fēng"]
        },
        "answer_formula": "correct_pinyin",
        "options_generator": {
            "strategy": "common_mistakes",
            "mistakes": []
        },
        "explanation_template": "\"{word}\"的正确读音是 \"{answer}\"，需要多加练习生字认读。",
        "tags": ["拼音", "读音"],
        "knowledge_points": ["汉字拼音认读"],
        "max_variants": 20
    },
    {
        "template_id": "chinese_6-8_pinyin_003",
        "subject": "chinese",
        "age_group": "6-8",
        "difficulty": "beginner",
        "type": "single_choice",
        "content_template": "下列哪个词语的拼音标注全部正确？",
        "variables": {
            "word": ["学校", "老师", "同学", "朋友", "读书"],
            "correct_pinyin": ["xué xiào", "lǎo shī", "tóng xué", "péng yǒu", "dú shū"]
        },
        "answer_formula": "correct_pinyin",
        "options_generator": {
            "strategy": "common_mistakes",
            "mistakes": []
        },
        "explanation_template": "\"{word}\"的正确拼音是 \"{answer}\"，注意每个字的声调。",
        "tags": ["拼音", "词语"],
        "knowledge_points": ["词语拼音认读"],
        "max_variants": 20
    },

    # ----------------------------------------------------------
    # 语文 6-8 岁：识字（2 个）
    # ----------------------------------------------------------
    {
        "template_id": "chinese_6-8_literacy_001",
        "subject": "chinese",
        "age_group": "6-8",
        "difficulty": "beginner",
        "type": "single_choice",
        "content_template": "\"{word}\"字的部首是什么？",
        "variables": {
            "word": ["明", "花", "草", "河", "树"],
            "radical": ["日", "艹", "艹", "氵", "木"]
        },
        "answer_formula": "radical",
        "options_generator": {
            "strategy": "common_mistakes",
            "mistakes": []
        },
        "explanation_template": "\"{word}\"的部首是 \"{answer}\"，认识部首有助于理解和记忆汉字。",
        "tags": ["识字", "部首"],
        "knowledge_points": ["汉字部首认识"],
        "max_variants": 20
    },
    {
        "template_id": "chinese_6-8_literacy_002",
        "subject": "chinese",
        "age_group": "6-8",
        "difficulty": "beginner",
        "type": "single_choice",
        "content_template": "下列哪个词与\"{word}\"是同类词语？",
        "variables": {
            "word": ["苹果", "小狗", "红色", "铅笔"],
            "category_options": {
                "苹果": [["香蕉", "西瓜", "橘子"], ["桌子", "铅笔", "天空"]],
                "小狗": [["小猫", "小兔", "小鸟"], ["书本", "汽车", "花朵"]],
                "红色": [["蓝色", "绿色", "黄色"], ["大树", "小河", "太阳"]],
                "铅笔": [["橡皮", "尺子", "书包"], ["小猫", "蓝天", "苹果"]]
            }
        },
        "answer_formula": "correct_option",
        "options_generator": {
            "strategy": "common_mistakes",
            "mistakes": []
        },
        "explanation_template": "\"{word}\"属于{category}类词语，\"{answer}\"也是同类词语。",
        "tags": ["识字", "词语分类"],
        "knowledge_points": ["词语归类"],
        "max_variants": 20
    },

    # ----------------------------------------------------------
    # 科学 6-8 岁：动植物（3 个）
    # ----------------------------------------------------------
    {
        "template_id": "science_6-8_animal_001",
        "subject": "science",
        "age_group": "6-8",
        "difficulty": "beginner",
        "type": "single_choice",
        "content_template": "{animal}属于哪一类动物？",
        "variables": {
            "animal": ["蜜蜂", "蝴蝶", "蚂蚁", "蜻蜓", "七星瓢虫"],
            "animal_class": ["昆虫", "昆虫", "昆虫", "昆虫", "昆虫"]
        },
        "answer_formula": "animal_class",
        "options_generator": {
            "strategy": "common_mistakes",
            "mistakes": []
        },
        "explanation_template": "{animal}的身体分为头、胸、腹三部分，有{legs}条腿和翅膀，属于{answer}。",
        "tags": ["动物", "昆虫"],
        "knowledge_points": ["昆虫的认识"],
        "max_variants": 20
    },
    {
        "template_id": "science_6-8_plant_001",
        "subject": "science",
        "age_group": "6-8",
        "difficulty": "beginner",
        "type": "single_choice",
        "content_template": "植物生长需要下列哪种条件？",
        "variables": {
            "condition": ["阳光", "水分", "空气", "土壤"],
            "category": ["光照", "水分", "空气", "养分"]
        },
        "answer_formula": "condition",
        "options_generator": {
            "strategy": "common_mistakes",
            "mistakes": []
        },
        "explanation_template": "植物生长需要阳光、水分、空气和适宜的温度等条件。{answer}是植物生长不可缺少的{category}条件。",
        "tags": ["植物", "生长条件"],
        "knowledge_points": ["植物生长的基本条件"],
        "max_variants": 20
    },
    {
        "template_id": "science_6-8_animal_002",
        "subject": "science",
        "age_group": "6-8",
        "difficulty": "beginner",
        "type": "single_choice",
        "content_template": "下列动物中，哪种是哺乳动物？",
        "variables": {
            "animal": ["猫", "狗", "兔子", "牛"],
            "feature": ["胎生哺乳", "胎生哺乳", "胎生哺乳", "胎生哺乳"]
        },
        "answer_formula": "animal",
        "options_generator": {
            "strategy": "common_mistakes",
            "mistakes": []
        },
        "explanation_template": "{answer}是哺乳动物，它们的特点是{feature}、体表有毛。",
        "tags": ["动物", "哺乳动物"],
        "knowledge_points": ["哺乳动物的认识"],
        "max_variants": 20
    },
]


# ============================================================
# SeedBank —— 种子题库管理类
# ============================================================
class SeedBank:
    """
    种子题库管理器。
    负责种子模板的增删查、按条件筛选、以及 JSON 持久化。
    """

    def __init__(self):
        """初始化种子库，加载预置种子模板。"""
        self.seeds: dict[str, dict] = {}  # template_id -> seed
        # 加载预置种子
        for seed in BUILT_IN_SEEDS:
            self.seeds[seed["template_id"]] = copy.deepcopy(seed)

    def add_seed(self, seed: dict) -> None:
        """
        添加一个种子模板到题库中。
        如果 template_id 已存在，则覆盖旧模板。

        Args:
            seed: 种子模板字典，必须包含 template_id 字段。
        """
        template_id = seed.get("template_id")
        if not template_id:
            raise ValueError("种子模板缺少 template_id 字段")
        self.seeds[template_id] = copy.deepcopy(seed)

    def remove_seed(self, template_id: str) -> None:
        """
        删除指定 template_id 的种子模板。

        Args:
            template_id: 种子模板的唯一标识。

        Raises:
            KeyError: 如果模板不存在。
        """
        if template_id not in self.seeds:
            raise KeyError(f"种子模板 '{template_id}' 不存在")
        del self.seeds[template_id]

    def get_seeds(
        self,
        subject: str = None,
        age_group: str = None,
        difficulty: str = None,
    ) -> list[dict]:
        """
        按条件筛选种子模板。支持学科、年龄段、难度的任意组合筛选。

        Args:
            subject: 学科过滤，如 "math"、"chinese"、"science"，为 None 则不过滤。
            age_group: 年龄段过滤，如 "6-8"、"9-12"，为 None 则不过滤。
            difficulty: 难度过滤，如 "beginner"、"intermediate"，为 None 则不过滤。

        Returns:
            符合条件的种子模板列表。
        """
        results = []
        for seed in self.seeds.values():
            if subject is not None and seed.get("subject") != subject:
                continue
            if age_group is not None and seed.get("age_group") != age_group:
                continue
            if difficulty is not None and seed.get("difficulty") != difficulty:
                continue
            results.append(copy.deepcopy(seed))
        return results

    def get_seed(self, template_id: str) -> Optional[dict]:
        """
        根据模板 ID 获取单个种子模板。

        Args:
            template_id: 种子模板的唯一标识。

        Returns:
            种子模板字典，如果不存在则返回 None。
        """
        seed = self.seeds.get(template_id)
        if seed is None:
            return None
        return copy.deepcopy(seed)

    def load_from_json(self, filepath: str) -> None:
        """
        从 JSON 文件加载种子库。文件内容应为种子模板列表或字典。

        Args:
            filepath: JSON 文件路径。
        """
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 支持列表或 {template_id: seed} 字典格式
        if isinstance(data, list):
            for seed in data:
                self.add_seed(seed)
        elif isinstance(data, dict):
            for template_id, seed in data.items():
                seed["template_id"] = template_id
                self.add_seed(seed)
        else:
            raise ValueError("JSON 文件格式不正确，应为列表或字典")

    def save_to_json(self, filepath: str) -> None:
        """
        将种子库保存到 JSON 文件。

        Args:
            filepath: JSON 文件保存路径。
        """
        data = list(self.seeds.values())
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def count(self) -> int:
        """返回当前种子库中的模板总数。"""
        return len(self.seeds)


# ============================================================
# VariantGenerator —— 变式题生成引擎
# ============================================================
class VariantGenerator:
    """
    变式题生成引擎。
    根据种子模板中的变量定义，通过随机参数替换生成变式题目。
    """

    def __init__(self, seed_bank: SeedBank):
        """
        初始化变式生成器。

        Args:
            seed_bank: 种子题库实例，用于获取种子模板。
        """
        self.seed_bank = seed_bank
        self._last_var_values: dict = {}  # 最近一次生成的变量值，供选项生成使用

    # ----------------------------------------------------------
    # 公开接口
    # ----------------------------------------------------------
    def generate_variant(self, template_id: str, count: int = 10) -> list[dict]:
        """
        从单个种子模板生成指定数量的变式题。

        Args:
            template_id: 种子模板的唯一标识。
            count: 需要生成的变式题数量，不超过种子的 max_variants。

        Returns:
            生成的变式题列表，每个题目是一个完整的字典。
        """
        seed = self.seed_bank.get_seed(template_id)
        if seed is None:
            raise ValueError(f"种子模板 '{template_id}' 不存在")

        max_variants = seed.get("max_variants", 20)
        actual_count = min(count, max_variants)

        variants = []
        existing_contents = []  # 用于去重

        max_attempts = actual_count * 10  # 最大尝试次数，防止无限循环
        attempts = 0

        while len(variants) < actual_count and attempts < max_attempts:
            attempts += 1
            question = self._build_variant(seed)
            if question is None:
                continue

            # 检查与已有变式是否重复
            if self._check_collision(question, existing_contents):
                continue

            existing_contents.append(question)
            variants.append(question)

        return variants

    def generate_batch(
        self,
        subject: str,
        age_group: str,
        difficulty: str = None,
        count_per_seed: int = 10,
    ) -> list[dict]:
        """
        批量生成变式题。从符合条件的所有种子中各生成指定数量的变式。

        Args:
            subject: 学科。
            age_group: 年龄段。
            difficulty: 难度（可选）。
            count_per_seed: 每个种子生成的变式题数量。

        Returns:
            所有生成的变式题列表。
        """
        seeds = self.seed_bank.get_seeds(
            subject=subject,
            age_group=age_group,
            difficulty=difficulty,
        )

        all_variants = []
        for seed in seeds:
            variants = self.generate_variant(
                seed["template_id"], count=count_per_seed
            )
            all_variants.extend(variants)

        # 打乱顺序
        random.shuffle(all_variants)
        return all_variants

    # ----------------------------------------------------------
    # 内部方法
    # ----------------------------------------------------------
    def _build_variant(self, seed: dict) -> Optional[dict]:
        """
        根据种子模板构建一个变式题目。

        Args:
            seed: 种子模板字典。

        Returns:
            完整的变式题目字典，如果构建失败（如约束不满足）则返回 None。
        """
        try:
            variables_def = seed.get("variables", {})
            # 生成随机变量值
            var_values = self._sample_variables(variables_def)
            if var_values is None:
                return None  # 约束不满足

            # 填充题目内容
            content, _ = self._fill_variables(
                seed["content_template"], var_values, variables_def
            )

            # 计算答案
            answer = self._evaluate_formula(seed["answer_formula"], var_values)

            # 保存变量值供选项生成器使用
            self._last_var_values = var_values.copy()

            # 生成选项
            options_gen = seed.get("options_generator", {})
            strategy = options_gen.get("strategy", "common_mistakes")
            mistakes = options_gen.get("mistakes", [])
            options = self._generate_options(
                answer, mistakes, strategy=strategy
            )
            if options is None:
                return None

            # 填充解析
            explanation = self._fill_explanation(
                seed.get("explanation_template", ""), var_values, answer
            )

            # 构建变式题目
            variant = {
                "content": content,
                "type": seed.get("type", "single_choice"),
                "options": options,
                "answer": answer,
                "explanation": explanation,
                "subject": seed.get("subject"),
                "age_group": seed.get("age_group"),
                "difficulty": seed.get("difficulty"),
                "variant_group_id": seed["template_id"],
                "tags": seed.get("tags", []),
                "knowledge_points": seed.get("knowledge_points", []),
            }
            return variant

        except Exception:
            # 生成过程中的任何异常都跳过该变式
            return None

    def _sample_variables(self, variables_def: dict) -> Optional[dict]:
        """
        根据变量定义生成一组随机变量值。
        支持列表选择（如 name）和整数范围生成（如 a、b），以及约束检查。

        Args:
            variables_def: 变量定义字典。

        Returns:
            变量名到值的映射字典，如果约束不满足则返回 None。
        """
        # 最多尝试 50 次来满足所有约束
        for _ in range(50):
            values = {}
            all_ok = True

            for var_name, var_config in variables_def.items():
                if isinstance(var_config, list):
                    # 列表类型：随机选择一个值
                    values[var_name] = random.choice(var_config)
                elif isinstance(var_config, dict):
                    var_type = var_config.get("type")
                    if var_type == "int":
                        # 整数范围类型
                        min_val = var_config.get("min", 0)
                        max_val = var_config.get("max", 100)
                        values[var_name] = random.randint(min_val, max_val)
                    elif var_type == "float":
                        min_val = var_config.get("min", 0.0)
                        max_val = var_config.get("max", 1.0)
                        values[var_name] = round(random.uniform(min_val, max_val), 2)
                    else:
                        values[var_name] = random.choice(var_config.get("values", []))
                else:
                    values[var_name] = var_config

            # 检查所有约束
            for var_name, var_config in variables_def.items():
                if isinstance(var_config, dict):
                    constraint = var_config.get("constraint")
                    if constraint:
                        if not self._check_constraint(constraint, values):
                            all_ok = False
                            break

            if all_ok:
                # 对于识字模板中的联动变量，需要特殊处理
                self._resolve_linked_variables(values, variables_def)
                return values

        return None  # 多次尝试后仍无法满足约束

    def _check_constraint(self, constraint: str, values: dict) -> bool:
        """
        检查约束条件是否满足。
        约束是一个简单的 Python 表达式字符串，变量从 values 中获取。

        Args:
            constraint: 约束表达式，如 "b < a"。
            values: 当前变量值字典。

        Returns:
            约束是否满足。
        """
        try:
            # 只允许简单的比较表达式，使用 eval 但限制可用变量
            safe_dict = {"abs": abs, "int": int, "float": float}
            safe_dict.update(values)
            return bool(eval(constraint, {"__builtins__": {}}, safe_dict))
        except Exception:
            return False

    def _resolve_linked_variables(self, values: dict, variables_def: dict) -> None:
        """
        处理联动变量。某些变量的值依赖于另一个变量的选择。
        例如：word 选中后，correct_pinyin 需要对应。

        Args:
            values: 当前变量值字典（会被就地修改）。
            variables_def: 变量定义字典。
        """
        # 处理拼音类模板：word 和 correct_pinyin 的联动
        if "word" in values and "correct_pinyin" in variables_def:
            word_list = variables_def["word"]
            pinyin_list = variables_def["correct_pinyin"]
            if isinstance(word_list, list) and isinstance(pinyin_list, list):
                try:
                    idx = word_list.index(values["word"])
                    values["correct_pinyin"] = pinyin_list[idx]
                except (ValueError, IndexError):
                    pass

        # 处理识字部首模板：word 和 radical 的联动
        if "word" in values and "radical" in variables_def:
            word_list = variables_def["word"]
            radical_list = variables_def["radical"]
            if isinstance(word_list, list) and isinstance(radical_list, list):
                try:
                    idx = word_list.index(values["word"])
                    values["radical"] = radical_list[idx]
                except (ValueError, IndexError):
                    pass

        # 处理动物类别模板：animal 和 animal_class 的联动
        if "animal" in values and "animal_class" in variables_def:
            animal_list = variables_def["animal"]
            animal_class_list = variables_def["animal_class"]
            if isinstance(animal_list, list) and isinstance(animal_class_list, list):
                try:
                    idx = animal_list.index(values["animal"])
                    values["animal_class"] = animal_class_list[idx]
                except (ValueError, IndexError):
                    pass

        # 处理动物特征模板：animal 和 feature 的联动
        if "animal" in values and "feature" in variables_def:
            animal_list = variables_def["animal"]
            feature_list = variables_def["feature"]
            if isinstance(animal_list, list) and isinstance(feature_list, list):
                try:
                    idx = animal_list.index(values["animal"])
                    values["feature"] = feature_list[idx]
                except (ValueError, IndexError):
                    pass

        # 处理植物条件模板：condition 和 category 的联动
        if "condition" in values and "category" in variables_def:
            condition_list = variables_def["condition"]
            category_list = variables_def["category"]
            if isinstance(condition_list, list) and isinstance(category_list, list):
                try:
                    idx = condition_list.index(values["condition"])
                    values["category"] = category_list[idx]
                except (ValueError, IndexError):
                    pass

        # 处理词语分类模板：word 和 category_options 的联动
        if "word" in values and "category_options" in variables_def:
            category_options = variables_def["category_options"]
            word = values["word"]
            if word in category_options:
                options_data = category_options[word]
                # options_data[0] 是正确选项列表，随机选一个作为答案
                values["correct_option"] = random.choice(options_data[0])
                values["_distractor_options"] = options_data[1]

        # 处理昆虫腿数
        if "animal" in values and "animal_class" in values:
            if values.get("animal_class") == "昆虫":
                values["legs"] = 6

    def _fill_variables(
        self, template: str, variables: dict, config: dict
    ) -> tuple[str, dict]:
        """
        用变量值填充模板字符串中的占位符。

        Args:
            template: 包含 {variable} 占位符的模板字符串。
            variables: 变量名到值的映射。
            config: 变量定义（用于确定值的格式化方式）。

        Returns:
            (filled_content, variable_values) 元组。
        """
        # 格式化变量值用于显示
        display_values = {}
        for key, val in variables.items():
            if isinstance(val, float) and val == int(val):
                display_values[key] = str(int(val))
            else:
                display_values[key] = str(val)

        filled = template.format(**display_values)
        return filled, variables

    def _evaluate_formula(self, formula: str, values: dict) -> any:
        """
        计算答案公式。
        支持简单算术表达式和变量引用。

        对于 "a + b" 形式的公式，直接计算。
        对于 "a*d + b*c, b*d" 形式（分子, 分母），返回 "分子/分母" 格式字符串。
        对于单个变量名，返回该变量的值。

        Args:
            formula: 答案公式字符串。
            values: 变量值字典。

        Returns:
            计算得到的答案值。
        """
        # 如果公式是单个变量名，直接返回对应的值
        if re.match(r'^[a-zA-Z_]\w*$', formula.strip()):
            val = values.get(formula.strip())
            if val is not None:
                return val

        # 检查是否为"分子, 分母"格式（分数运算）
        if "," in formula:
            parts = formula.split(",")
            if len(parts) == 2:
                safe_dict = {"abs": abs, "int": int, "float": float}
                safe_dict.update(values)
                num = eval(parts[0].strip(), {"__builtins__": {}}, safe_dict)
                den = eval(parts[1].strip(), {"__builtins__": {}}, safe_dict)
                # 约分化简
                num, den = self._simplify_fraction(num, den)
                values["answer_num"] = num
                values["answer_den"] = den
                return f"{num}/{den}"

        # 普通算术表达式
        try:
            safe_dict = {"abs": abs, "int": int, "float": float}
            safe_dict.update(values)
            result = eval(formula, {"__builtins__": {}}, safe_dict)
            # 如果结果是整数类型的浮点数，转为整数
            if isinstance(result, float) and result == int(result):
                result = int(result)
            return result
        except Exception:
            return None

    def _simplify_fraction(self, numerator: int, denominator: int) -> tuple[int, int]:
        """
        将分数化为最简分数。

        Args:
            numerator: 分子。
            denominator: 分母。

        Returns:
            (最简分子, 最简分母) 元组。
        """
        if denominator == 0:
            return numerator, 1

        # 处理负号：保证分母为正
        if denominator < 0:
            numerator = -numerator
            denominator = -denominator

        # 计算最大公约数
        def gcd(a, b):
            while b:
                a, b = b, a % b
            return a

        g = gcd(abs(numerator), abs(denominator))
        return numerator // g, denominator // g

    def _generate_options(
        self,
        answer,
        mistakes: list,
        strategy: str = "common_mistakes",
        options_count: int = 4,
    ) -> Optional[list[dict]]:
        """
        根据策略生成干扰选项。

        Args:
            answer: 正确答案。
            mistakes: 预设的错误答案公式列表（用于 common_mistakes 策略）。
            strategy: 选项生成策略，"common_mistakes" 或 "random_near"。
            options_count: 选项总数（含正确答案）。

        Returns:
            选项列表，每个选项是 {"label": "A"/"B"/..., "content": ..., "is_correct": bool}。
            如果无法生成有效选项则返回 None。
        """
        labels = ["A", "B", "C", "D", "E", "F"]
        options = []

        if strategy == "common_mistakes" and mistakes:
            # 使用预设的错误答案公式生成干扰项
            distractors = []
            for mistake_formula in mistakes:
                try:
                    if isinstance(mistake_formula, str):
                        # 尝试计算公式
                        safe_dict = {"abs": abs, "int": int, "float": float}
                        safe_dict.update(self._last_var_values)
                        if "," in mistake_formula:
                            parts = mistake_formula.split(",")
                            if len(parts) == 2:
                                num = eval(parts[0].strip(), {"__builtins__": {}}, safe_dict)
                                den = eval(parts[1].strip(), {"__builtins__": {}}, safe_dict)
                                num, den = self._simplify_fraction(num, den)
                                val = f"{num}/{den}"
                            else:
                                continue
                        else:
                            val = eval(mistake_formula, {"__builtins__": {}}, safe_dict)
                            if isinstance(val, float) and val == int(val):
                                val = int(val)
                        distractors.append(val)
                    else:
                        distractors.append(mistake_formula)
                except Exception:
                    continue

            # 去重并过滤掉与正确答案相同的项
            distractors = list(set(distractors))
            distractors = [d for d in distractors if d != answer]

            # 如果正确答案是整数，优先保留整数干扰项（过滤掉不合理的非整数结果）
            if isinstance(answer, int):
                int_distractors = [d for d in distractors if isinstance(d, int)]
                non_int_distractors = [d for d in distractors if not isinstance(d, int)]
                # 将浮点但为整数的也归入整数组
                for d in non_int_distractors[:]:
                    if isinstance(d, float) and d == int(d):
                        int_distractors.append(int(d))
                distractors = int_distractors + non_int_distractors

            # 截取需要的数量
            distractors = distractors[: options_count - 1]

        elif strategy == "random_near":
            # 在正确答案附近随机偏移生成干扰项
            distractors = []
            if isinstance(answer, (int, float)):
                for _ in range(options_count - 1):
                    offset = random.choice([-3, -2, -1, 1, 2, 3])
                    wrong = answer + offset
                    if wrong != answer and wrong not in distractors:
                        distractors.append(wrong)
                # 如果不够，补充预设错误
                if len(distractors) < options_count - 1:
                    for m in mistakes:
                        try:
                            safe_dict = {"abs": abs, "int": int, "float": float}
                            safe_dict.update(self._last_var_values)
                            val = eval(m, {"__builtins__": {}}, safe_dict)
                            if isinstance(val, float) and val == int(val):
                                val = int(val)
                            if val != answer and val not in distractors:
                                distractors.append(val)
                        except Exception:
                            continue
                        if len(distractors) >= options_count - 1:
                            break
            else:
                # 非数值类型的随机_near 退化为使用预设错误
                for m in mistakes:
                    try:
                        if isinstance(m, str):
                            safe_dict = {"abs": abs, "int": int, "float": float}
                            safe_dict.update(self._last_var_values)
                            val = eval(m, {"__builtins__": {}}, safe_dict)
                            if val != answer:
                                distractors.append(val)
                        else:
                            if m != answer:
                                distractors.append(m)
                    except Exception:
                        continue
                    if len(distractors) >= options_count - 1:
                        break

            distractors = distractors[: options_count - 1]

        else:
            # 未知策略，尝试生成一些简单干扰项
            distractors = []
            if isinstance(answer, (int, float)):
                for offset in [1, -1, 2, -2]:
                    wrong = answer + offset
                    if wrong != answer:
                        distractors.append(wrong)
                    if len(distractors) >= options_count - 1:
                        break
            distractors = distractors[: options_count - 1]

        # 如果干扰项不够，填充占位
        while len(distractors) < options_count - 1:
            distractors.append("无法确定")

        # 格式化答案显示
        answer_str = self._format_answer(answer)

        # 构建选项列表
        options.append({
            "label": "A",
            "content": answer_str,
            "is_correct": True,
        })

        for i, distractor in enumerate(distractors):
            label = labels[i + 1]
            options.append({
                "label": label,
                "content": self._format_answer(distractor),
                "is_correct": False,
            })

        # 打乱选项顺序
        random.shuffle(options)

        # 重新分配标签
        for i, opt in enumerate(options):
            opt["label"] = labels[i]

        return options

    def _format_answer(self, answer) -> str:
        """
        格式化答案为字符串用于显示。

        Args:
            answer: 答案值。

        Returns:
            格式化后的字符串。
        """
        if isinstance(answer, float):
            if answer == int(answer):
                return str(int(answer))
            return str(round(answer, 2))
        return str(answer)

    def _fill_explanation(self, template: str, values: dict, answer) -> str:
        """
        填充解析模板，生成最终的解析文本。

        Args:
            template: 解析模板字符串。
            values: 变量值字典。
            answer: 计算得到的答案。

        Returns:
            填充后的解析文本。
        """
        if not template:
            return ""

        # 准备显示值
        display_values = {}
        for key, val in values.items():
            if isinstance(val, float) and val == int(val):
                display_values[key] = str(int(val))
            else:
                display_values[key] = str(val)

        # 添加特殊变量
        display_values["answer"] = self._format_answer(answer)
        display_values["answer_num"] = str(values.get("answer_num", ""))
        display_values["answer_den"] = str(values.get("answer_den", ""))

        # 添加方程模板中需要的中间变量
        if "a" in values and "b" in values and "c" in values:
            display_values["c_minus_b"] = str(values["c"] - values["b"])
            display_values["c_plus_b"] = str(values["c"] + values["b"])

        try:
            return template.format(**display_values)
        except (KeyError, IndexError):
            # 如果模板中有变量缺失，返回原始模板
            return template

    def _check_collision(self, question: dict, existing: list[dict]) -> bool:
        """
        检查新生成的题目是否与已有题目重复。
        通过比较题目内容文本来判断是否重复。

        Args:
            question: 新生成的变式题目。
            existing: 已有的变式题目列表。

        Returns:
            True 表示存在重复（碰撞），False 表示不重复。
        """
        new_content = question.get("content", "").strip()
        for existing_question in existing:
            if existing_question.get("content", "").strip() == new_content:
                return True
        return False


# ============================================================
# 便捷函数
# ============================================================

def create_seed_bank() -> SeedBank:
    """创建并返回一个预装了内置种子模板的 SeedBank 实例。"""
    return SeedBank()


def create_variant_generator(seed_bank: SeedBank = None) -> VariantGenerator:
    """
    创建并返回一个 VariantGenerator 实例。
    如果未提供 seed_bank，则自动创建一个。

    Args:
        seed_bank: 可选的 SeedBank 实例。

    Returns:
        VariantGenerator 实例。
    """
    if seed_bank is None:
        seed_bank = SeedBank()
    return VariantGenerator(seed_bank)


# ============================================================
# 模块入口：当直接运行时进行简单演示
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("种子题库与变式生成引擎 - 演示")
    print("=" * 60)

    # 创建种子库
    bank = SeedBank()
    print(f"\n[1] 种子库已初始化，共 {bank.count()} 个种子模板")

    # 按条件筛选
    math_seeds = bank.get_seeds(subject="math", age_group="6-8")
    print(f"[2] 筛选 数学 6-8 岁种子: {len(math_seeds)} 个")
    for s in math_seeds:
        print(f"    - {s['template_id']}: {s['tags']}")

    # 创建变式生成器
    generator = VariantGenerator(bank)

    # 从单个种子生成变式
    print(f"\n[3] 从种子 math_6-8_sub_001 生成 5 个变式题:")
    variants = generator.generate_variant("math_6-8_sub_001", count=5)
    for i, v in enumerate(variants, 1):
        print(f"\n  变式 #{i}:")
        print(f"    题目: {v['content']}")
        options_str = ", ".join(
            [f"{o['label']}.{o['content']}" for o in v['options']]
        )
        print(f"    选项: {options_str}")
        print(f"    解析: {v['explanation']}")

    # 批量生成
    print(f"\n[4] 批量生成 数学 9-12 岁变式题 (每种子 3 个):")
    batch = generator.generate_batch(
        subject="math", age_group="9-12", count_per_seed=3
    )
    print(f"  共生成 {len(batch)} 个变式题")
    for i, v in enumerate(batch[:3], 1):
        print(f"  [{i}] {v['content']}")

    # JSON 持久化演示
    import os
    demo_path = os.path.join(
        os.path.dirname(__file__), "_seed_bank_demo.json"
    )
    bank.save_to_json(demo_path)
    print(f"\n[5] 种子库已保存到: {demo_path}")

    # 从文件加载
    bank2 = SeedBank()
    bank2.load_from_json(demo_path)
    print(f"[6] 从文件加载后种子库共 {bank2.count()} 个模板")

    # 清理演示文件
    os.remove(demo_path)
    print(f"[7] 演示文件已清理")

    print("\n" + "=" * 60)
    print("演示结束")
    print("=" * 60)
