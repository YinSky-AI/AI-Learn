# -*- coding: utf-8 -*-
"""
Pydantic Schema 包初始化模块

该包定义所有 API 的请求/响应数据模型（Pydantic Schema），
用于请求参数校验、响应数据序列化和 API 文档自动生成。

Schema 按业务域组织为多个模块：
- auth: 认证相关（注册、登录、Token）
- common: 通用响应格式（ApiResponse、分页响应等）
- user: 用户信息（创建、更新、响应）
- course: 课程与课时（CRUD 和关联模型）
- content: 内容相关（知识点、学科、年龄分级、题目）
- learning: 学习会话和答题记录
- question: AI 出题相关（生成请求、变式题、历史查询）
"""
