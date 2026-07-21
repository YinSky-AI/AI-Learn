"""知识图谱 MVP 的三学科静态层级。

图谱负责表达知识结构；用户掌握度始终来自行为报告，不在此处保存。
``mastery_keys`` 兼容当前题库的知识标签和历史知识节点标题。
"""

from __future__ import annotations

from typing import Any


def _leaf(node_id: str, name: str, description: str, *mastery_keys: str) -> dict[str, Any]:
    return {
        "id": node_id,
        "name": name,
        "description": description,
        "mastery_keys": (name, *mastery_keys),
    }


KNOWLEDGE_GRAPHS: dict[str, dict[str, Any]] = {
    "math": {
        "id": "math",
        "name": "数学",
        "children": [
            {
                "id": "math-number-operations",
                "name": "数与运算",
                "description": "理解数的意义，并能准确完成常见运算。",
                "children": [
                    _leaf("math-integer-operations", "整数运算", "从数的认识到四则运算，建立稳定的计算基础。", "10以内运算", "20以内运算", "数学 - 6-8岁 - 简单"),
                    _leaf("math-fraction-operations", "分数运算", "理解分数意义，掌握通分、约分与分数四则运算。", "异分母分数加法", "通分", "数学 - 9-12岁 - 中等"),
                    _leaf("math-decimal-operations", "小数运算", "掌握小数的比较、互化与四则运算。", "小数", "小数加法", "小数乘法", "数学 - 9-12岁 - 简单"),
                ],
            },
            {
                "id": "math-geometry",
                "name": "图形与几何",
                "description": "从图形识别逐步发展空间想象与几何推理。",
                "children": [
                    _leaf("math-basic-shapes", "基础图形", "认识三角形、长方形、正方形和圆等常见图形。", "图形认知", "三角形", "长方形"),
                    _leaf("math-area-perimeter", "周长与面积", "理解周长、面积的含义并能解决实际问题。", "周长", "面积", "面积/周长", "几何面积"),
                    _leaf("math-solid-geometry", "立体几何", "认识长方体、正方体等立体图形及其体积。", "长方体", "正方体", "体积计算"),
                ],
            },
            {
                "id": "math-algebra-data",
                "name": "代数与数据",
                "description": "用符号、方程和统计方法描述数量关系。",
                "children": [
                    _leaf("math-equations", "方程", "理解等量关系，并能列方程、解方程。", "一元一次方程", "方程求解", "简易方程"),
                    _leaf("math-ratio", "比和比例", "理解比、比例和百分数在生活中的应用。", "比例", "比例应用", "百分数"),
                    _leaf("math-statistics", "数据统计", "会读取统计图表并用平均数等指标分析数据。", "统计图表", "平均数", "数据分析"),
                ],
            },
        ],
    },
    "chinese": {
        "id": "chinese",
        "name": "语文",
        "children": [
            {
                "id": "chinese-language-foundation",
                "name": "字词基础",
                "description": "建立规范、准确的汉语言文字基础。",
                "children": [
                    _leaf("chinese-pinyin", "拼音", "掌握声母、韵母、声调与整体认读音节。", "声母", "韵母", "整体认读"),
                    _leaf("chinese-characters", "汉字", "认识常用汉字，理解部首、笔顺和字义。", "常见字", "笔顺", "部首", "语文 - 6-8岁 - 简单"),
                    _leaf("chinese-words-idioms", "词语与成语", "在语境中理解并正确使用词语和成语。", "词语", "词语搭配", "成语", "成语运用"),
                ],
            },
            {
                "id": "chinese-reading",
                "name": "阅读理解",
                "description": "理解不同文体的内容、结构与表达作用。",
                "children": [
                    _leaf("chinese-narrative", "记叙文阅读", "抓住人物、事件与线索，体会文章情感。", "记叙文-要素", "记叙文-表达"),
                    _leaf("chinese-expository", "说明文阅读", "识别说明对象、顺序和常见说明方法。", "说明文方法", "说明方法", "说明顺序"),
                    _leaf("chinese-classics", "古诗文", "理解古诗词和文言文的内容、意象与情感。", "古诗词", "古诗赏析", "文言文", "古文翻译"),
                ],
            },
            {
                "id": "chinese-expression",
                "name": "语言表达",
                "description": "在阅读与写作中准确、清晰、有条理地表达。",
                "children": [
                    _leaf("chinese-rhetoric", "修辞与语病", "辨析修辞手法、病句和标点使用。", "修辞手法", "病句辨析", "标点符号"),
                    _leaf("chinese-writing", "写作", "围绕主题组织材料，完成连贯、具体的表达。", "写作要求", "应用文写作", "演讲稿"),
                    _leaf("chinese-literature", "文学常识", "积累重要作家、作品与常见文体知识。", "作家作品", "文体知识", "名著阅读"),
                ],
            },
        ],
    },
    "english": {
        "id": "english",
        "name": "英语",
        "children": [
            {
                "id": "english-language-foundation",
                "name": "语音与词汇",
                "description": "建立从字母发音到词汇运用的语言基础。",
                "children": [
                    _leaf("english-phonics", "自然拼读", "建立字母组合与发音之间的联系。", "phonics", "letter_sounds", "vowel_sounds"),
                    _leaf("english-vocabulary", "基础词汇", "在主题语境中理解、拼写并运用常用词汇。", "vocabulary", "spelling", "英语 - 6-8岁 - 简单"),
                    _leaf("english-sentence-patterns", "基础句型", "理解常用句子结构并完成简单表达。", "sentence_pattern", "sentence_structure", "简单句型"),
                ],
            },
            {
                "id": "english-grammar",
                "name": "语法",
                "description": "用语法规则准确理解和组织英语句子。",
                "children": [
                    _leaf("english-tenses", "时态", "掌握一般时、进行时、完成时等常见时态。", "tense", "tenses", "simple_present", "simple_past", "present_perfect"),
                    _leaf("english-clauses", "从句", "理解定语、宾语和状语从句的结构与作用。", "定语从句", "宾语从句", "状语从句"),
                    _leaf("english-nonfinite", "非谓语动词", "辨析并运用不定式、动名词和分词。", "nonfinite_verbs", "非谓语动词"),
                ],
            },
            {
                "id": "english-comprehensive",
                "name": "综合运用",
                "description": "在阅读和写作任务中综合运用语言知识。",
                "children": [
                    _leaf("english-reading", "阅读理解", "获取主旨、细节并进行合理推断。", "reading", "reading_comprehension", "detail_question"),
                    _leaf("english-cloze", "完形填空", "结合语境、词汇和语法补全篇章。", "cloze", "完形填空"),
                    _leaf("english-writing", "英语写作", "围绕任务清晰、连贯地组织英文表达。", "writing", "sentence_writing", "应用文写作"),
                ],
            },
        ],
    },
}


SUBJECT_ALIASES = {
    "math": "math",
    "数学": "math",
    "SUBJ_MATH": "math",
    "chinese": "chinese",
    "语文": "chinese",
    "SUBJ_CHINESE": "chinese",
    "english": "english",
    "英语": "english",
    "SUBJ_ENGLISH": "english",
}
