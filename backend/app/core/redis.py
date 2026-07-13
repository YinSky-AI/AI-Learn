# -*- coding: utf-8 -*-
"""
Redis 连接管理模块
提供 Redis 客户端单例和常用操作封装
"""

import json
from typing import Any, Optional

import redis.asyncio as aioredis

from app.core.config import settings


class RedisClient:
    """Redis 异步客户端封装"""

    def __init__(self):
        self._client: Optional[aioredis.Redis] = None

    async def init(self) -> None:
        """初始化 Redis 连接"""
        if self._client is None:
            self._client = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                max_connections=20,
            )

    async def close(self) -> None:
        """关闭 Redis 连接"""
        if self._client is not None:
            await self._client.close()
            self._client = None

    @property
    def client(self) -> aioredis.Redis:
        """获取 Redis 客户端"""
        if self._client is None:
            raise RuntimeError("Redis 未初始化，请先调用 init()")
        return self._client

    async def get(self, key: str) -> Optional[str]:
        """获取缓存值"""
        return await self.client.get(key)

    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> None:
        """设置缓存值"""
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        await self.client.set(key, value, ex=expire)

    async def delete(self, key: str) -> None:
        """删除缓存"""
        await self.client.delete(key)

    async def exists(self, key: str) -> bool:
        """判断 key 是否存在"""
        return bool(await self.client.exists(key))

    async def incr(self, key: str) -> int:
        """自增计数"""
        return await self.client.incr(key)

    async def expire(self, key: str, seconds: int) -> None:
        """设置过期时间"""
        await self.client.expire(key, seconds)

    async def ttl(self, key: str) -> int:
        """获取剩余过期时间"""
        return await self.client.ttl(key)

    async def keys(self, pattern: str) -> list:
        """按模式查询 key"""
        return await self.client.keys(pattern)

    async def hset(self, name: str, key: str, value: Any) -> None:
        """设置哈希字段"""
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        await self.client.hset(name, key, value)

    async def hget(self, name: str, key: str) -> Optional[str]:
        """获取哈希字段"""
        return await self.client.hget(name, key)

    async def hgetall(self, name: str) -> dict:
        """获取哈希所有字段"""
        return await self.client.hgetall(name)


# Redis 全局客户端单例
redis_client = RedisClient()
