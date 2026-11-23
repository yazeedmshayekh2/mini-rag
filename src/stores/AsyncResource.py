from abc import ABC, abstractmethod


class AsyncResource(ABC):
    @abstractmethod
    async def close(self) -> None: ...

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()
