import redis
import json
import hashlib
from typing import Optional, Dict, Any

class SemanticCache:
    def __init__(self, host='localhost', port=6379, db=0):
        self.redis = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        self.ttl = 3600  # 1 hour

    def _get_cache_key(self, query: str) -> str:
        """Generate cache key from query."""
        return hashlib.md5(query.encode()).hexdigest()

    def _is_similar(self, query1: str, query2: str, threshold: float = 0.8) -> bool:
        """Simple similarity check (can be improved with embeddings)."""
        # For now, exact match or substring
        return query1.lower() in query2.lower() or query2.lower() in query1.lower()

    def get(self, query: str) -> Optional[Dict[str, Any]]:
        """Retrieve from cache if similar query exists."""
        keys = self.redis.keys('*')
        for key in keys:
            cached_query = self.redis.hget(key, 'query')
            if cached_query and self._is_similar(query, cached_query):
                result = self.redis.hgetall(key)
                if result:
                    return json.loads(result.get('response', '{}'))
        return None

    def set(self, query: str, response: Dict[str, Any]):
        """Store response in cache."""
        key = self._get_cache_key(query)
        data = {
            'query': query,
            'response': json.dumps(response)
        }
        self.redis.hset(key, mapping=data)
        self.redis.expire(key, self.ttl)

    def clear(self):
        """Clear all cache."""
        self.redis.flushdb()