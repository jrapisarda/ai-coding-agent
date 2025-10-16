import time
import asyncio
from typing import Dict
from collections import defaultdict

class RateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, client_id: str) -> bool:
        async with self._lock:
            now = time.time()
            minute_ago = now - 60
            
            # Clean old requests
            self.requests[client_id] = [
                req_time for req_time in self.requests[client_id]
                if req_time > minute_ago
            ]
            
            # Check if under limit
            if len(self.requests[client_id]) < self.requests_per_minute:
                self.requests[client_id].append(now)
                return True
            
            return False
    
    def get_remaining_requests(self, client_id: str) -> int:
        now = time.time()
        minute_ago = now - 60
        recent_requests = [
            req_time for req_time in self.requests[client_id]
            if req_time > minute_ago
        ]
        return max(0, self.requests_per_minute - len(recent_requests))