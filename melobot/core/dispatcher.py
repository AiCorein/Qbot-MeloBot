import asyncio as aio
import traceback

from ..interface.core import IEventDispatcher
from ..interface.models import IEventHandler
from ..interface.typing import *
from ..models.event import BotEvent
from ..interface.exceptions import *
from ..interface.models import MsgEventHandler, ReqEventHandler, NoticeEventHandler
from ..utils.logger import Logger


class BotDispatcher(IEventDispatcher):
    """
    bot 调度模块。负责将传递的普通事件送入各事件总线
    （接收的事件类型：消息、请求和通知）
    """
    def __init__(self, logger: Logger) -> None:
        super().__init__()
        self._handlers: Dict[str, List[IEventHandler]] = {
            'message': [],
            'request': [],
            'notice': []
        }
        self.logger = logger

        self._ready_signal = aio.Event()

    def bind(self, all_handlers: List[IEventHandler]) -> None:
        """
        绑定事件处理器列表
        """
        for handler in all_handlers:
            if isinstance(handler, MsgEventHandler):
                self._handlers['message'].append(handler)
            elif isinstance(handler, ReqEventHandler):
                self._handlers['request'].append(handler)
            elif isinstance(handler, NoticeEventHandler):
                self._handlers['notice'].append(handler)
        for k in self._handlers.keys():
            self._handlers[k] = sorted(self._handlers[k], key=lambda x:x.priority, reverse=True)

        self._ready_signal.set()

    async def dispatch(self, event: BotEvent) -> None:
        """
        把事件分发到对应的事件总线
        """
        await self._ready_signal.wait()

        try:
            permit_priority = PriorityLevel.MIN.value
            handlers = self._handlers[event.type]
            for handler in handlers:
                # 事件处理器优先级不够，则不分配给它处理
                if handler.priority < permit_priority:
                    continue
                # evoke 返回的值用于判断，事件处理器内部经过各种检查后，是否选择处理这个事件。
                if not (await handler.evoke(event)):
                    # 如果决定不处理，则会跳过此次循环（也就是不进行“可能存在的优先级阻断操作”）
                    continue
                if handler.set_block and handler.priority > permit_priority:
                    permit_priority = handler.priority
        except Exception as e:
            self.logger.error(f"bot dispatcher 抛出异常：[{e.__class__.__name__}] {e}")
            self.logger.debug(f"异常点的事件记录为：{event.raw}")
            self.logger.debug('异常回溯栈：\n' + traceback.format_exc().strip('\n'))