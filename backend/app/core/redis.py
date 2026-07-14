# -*- coding: utf-8 -*-
"""
Redis 连接管理模块

提供 Redis 异步客户端的单例封装，封装了常用的缓存操作（字符串、哈希、过期等），
并自动处理 dict/list 类型的 JSON 序列化/反序列化。

主要用途：
- API 速率限制的滑动窗口计数
- 用户会话和认证令牌的缓存
- 热点数据的缓存加速
- 分布式计数器和临时数据存储

使用方式：
    from app.core.redis import redis_client
    await redis_client.init()      # 应用启动时初始化
    await redis_client.set("key", value, expire=3600)
    value = await redis_client.get("key")
    await redis_client.close()     # 应用关闭时释放连接
"""

import json
from typing import Any, Optional

import redis.asyncio as aioredis

from app.core.config import settings


class RedisClient:
    """
    Redis 异步客户端封装类

    基于 redis.asyncio 的异步 Redis 客户端高级封装，提供连接生命周期管理和
    常用数据结构操作的便捷方法。支持自动 JSON 序列化，并作为全局单例使用。

    Attributes:
        _client: 内部的 aioredis.Redis 实例，未初始化时为 None

    Methods:
        init: 异步初始化 Redis 连接
        close: 异步关闭 Redis 连接
        get/set/delete: 字符串操作
        hset/hget/hgetall: 哈希操作
        incr/expire/ttl: 计数和过期管理
    """

    def __init__(self):
        """初始化 RedisClient 实例，此时未建立实际连接。"""
        self._client: Optional[aioredis.Redis] = None

    async def init(self) -> None:
        """
        初始化 Redis 连接

        根据 settings.REDIS_URL 创建异步 Redis 连接池。
        幂等操作：如果已初始化则直接返回，不会重复创建连接。

        Raises:
            无显式抛出，但底层连接异常会向上传播
        """
        if self._client is None:
            self._client = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                max_connections=20,
            )

    async def close(self) -> None:
        """
        关闭 Redis 连接

        安全关闭 Redis 连接池并释放资源。
        幂等操作：如果未初始化或未连接则直接返回。
        """
        if self._client is not None:
            await self._client.close()
            self._client = None

    @property
    def client(self) -> aioredis.Redis:
        """
        获取底层 Redis 客户端实例

        提供对底层 aioredis.Redis 的访问，以便执行封装中未提供的操作。

        Returns:
            aioredis.Redis: Redis 异步客户端实例

        Raises:
            RuntimeError: 如果 Redis 未初始化，提示先调用 init()
        """
        if self._client is None:
            raise RuntimeError("Redis 未初始化，请先调用 init()")
        return self._client

    async def get(self, key: str) -> Optional[str]:
        """
        获取缓存值

        Args:
            key: Redis 键名

        Returns:
            Optional[str]: 键对应的字符串值，键不存在时返回 None
        """
        return await self.client.get(key)

    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> None:
        """
        设置缓存值

        自动将 dict/list 类型的 value 序列化为 JSON 字符串存储。

        Args:
            key: Redis 键名
            value: 要存储的值，支持 str/int/float/dict/list 等类型
            expire: 过期时间（秒），None 表示永不过期
        """
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        await self.client.set(key, value, ex=expire)

    async def delete(self, key: str) -> None:
        """
        删除缓存键

        Args:
            key: 要删除的 Redis 键名
        """
        await self.client.delete(key)

    async def exists(self, key: str) -> bool:
        """
        判断 key 是否存在

        Args:
            key: Redis 键名

        Returns:
            bool: 键存在返回 True，否则返回 False
        """
        return bool(await self.client.exists(key))

    async def incr(self, key: str) -> int:
        """
        自增计数器

        将键对应的值原子性地增加 1。若键不存在则先初始化为 0 再自增。

        Args:
            key: 计数器键名

        Returns:
            int: 自增后的新值
        """
        return await self.client.incr(key)

    async def expire(self, key: str, seconds: int) -> None:
        """
        设置键的过期时间

        Args:
            key: Redis 键名
            seconds: 过期时间（秒）
        """
        await self.client.expire(key, seconds)

    async def ttl(self, key: str) -> int:
        """
        获取键的剩余过期时间

        Args:
            key: Redis 键名

        Returns:
            int: 剩余秒数，-1 表示键不存在或永不过期，-2 表示键不存在
        """
        return await self.client.ttl(key)

    async def keys(self, pattern: str) -> list:
        """
        按模式查询键列表

        注意：生产环境中谨慎使用，大数据量时可能阻塞 Redis。

        Args:
            pattern: 匹配模式，如 "user:*"

        Returns:
            list: 匹配到的键名列表
        """
        return await self.client.keys(pattern)

    async def hset(self, name: str, key: str, value: Any) -> None:
        """
        设置哈希表字段

        自动将 dict/list 类型的 value 序列化为 JSON 字符串。

        Args:
            name: 哈希表名称
            key: 字段名
            value: 字段值
        """
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        await self.client.hset(name, key, value)

    async def hget(self, name: str, key: str) -> Optional[str]:
        """
        获取哈希表字段值

        Args:
            name: 哈希表名称
            key: 字段名

        Returns:
            Optional[str]: 字段值，不存在时返回 None
        """
        return await self.client.hget(name, key)

    async def hgetall(self, name: str) -> dict:
        """
        获取哈希表所有字段和值

        Args:
            name: 哈希表名称

        Returns:
            dict: 包含所有字段和值的字典
        """
        return await self.client.hgetall(name)


# Redis 全局客户端单例
redis_client = RedisClient()
