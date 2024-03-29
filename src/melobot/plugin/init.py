import importlib.util
import os
import pathlib
import sys

from ..base.abc import (
    BotHookRunnerArgs,
    BotLife,
    EventHandlerArgs,
    PluginSignalHandlerArgs,
    ShareObjArgs,
    ShareObjCbArgs,
)
from ..base.exceptions import PluginInitError
from ..base.tools import to_async
from ..base.typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Literal,
    LogicMode,
    Optional,
    P,
    PriorLevel,
    Union,
)
from ..utils.checker import (
    AtChecker,
    FriendReqChecker,
    GroupReqChecker,
    NoticeTypeChecker,
)
from ..utils.matcher import (
    ContainMatcher,
    EndMatcher,
    FullMatcher,
    RegexMatcher,
    StartMatcher,
)
from .handler import (
    AllEventHandler,
    MetaEventHandler,
    MsgEventHandler,
    NoticeEventHandler,
    ReqEventHandler,
)

if TYPE_CHECKING:
    from ..base.abc import SessionRule, WrappedChecker
    from ..utils.checker import BotChecker
    from ..utils.matcher import BotMatcher
    from ..utils.parser import BotParser


class PluginProxy:
    """Bot 插件代理类。供外部使用."""

    def __init__(
        self,
        id: str,
        ver: str,
        desc: str,
        doc: str,
        keywords: list[str],
        url: str,
        share_objs: list[tuple[str, str]],
        share_cbs: list[tuple[str, str]],
        signal_methods: list[tuple[str, str]],
    ) -> None:
        self.id = id
        self.version = ver
        self.desc = desc
        self.doc = doc
        self.keywords = keywords
        self.url = url
        self.shares = share_objs
        self.share_cbs = share_cbs
        self.signal_methods = signal_methods


class PluginLoader:
    """插件加载器."""

    @staticmethod
    def load_from_dir(plugin_path: str) -> "BotPlugin":
        """从指定插件目录加载插件."""
        if not os.path.exists(os.path.join(plugin_path, "__init__.py")):
            raise PluginInitError(
                f"{plugin_path} 缺乏入口主文件 __init__.py，插件无法加载"
            )
        plugin_name = os.path.basename(plugin_path)
        plugins_folder = str(pathlib.Path(plugin_path).parent.resolve(strict=True))
        plugins_folder_name = os.path.basename(plugins_folder)
        if plugins_folder not in sys.path:
            importlib.import_module(plugins_folder_name)
            sys.path.insert(0, plugins_folder)
        module = importlib.import_module(
            f"{plugins_folder_name}.{plugin_name}", f"{plugins_folder_name}"
        )

        plugin = None
        for obj in module.__dict__.values():
            if isinstance(obj, BotPlugin):
                plugin = obj
                break
        if plugin is None:
            raise PluginInitError("指定的入口主文件中，未发现 Plugin 实例，无效导入")
        return plugin

    @staticmethod
    def load(target: Union[str, "BotPlugin"]) -> "BotPlugin":
        """加载插件."""
        if isinstance(target, str):
            plugin = PluginLoader.load_from_dir(target)
        else:
            plugin = target
        plugin._self_build()
        return plugin


class BotPlugin:
    """插件类，使用该类实例化一个插件

    同时该类会提供各种接口用于注册事件处理器、共享对象、共享对象回调方法和信号处理方法。
    """

    def __init__(
        self,
        id: str,
        version: str,
        desc: str = "",
        doc: str = "",
        keywords: Optional[list[str]] = None,
        url: str = "",
    ) -> None:
        """初始化一个插件

        :param id: 插件的 id
        :param version: 插件的版本
        :param desc: 插件功能描述
        :param doc: 插件简单的文档说明
        :param keywords: 关键词列表
        :param url: 插件项目地址
        """
        self.__id__ = id
        self.__version__ = version
        self.__desc__ = desc
        self.__keywords__ = keywords if keywords is not None else []
        self.__url__ = url
        self.__pdoc__ = doc

        self.__handler_args__: list[EventHandlerArgs] = []
        self.__signal_args__: list[PluginSignalHandlerArgs] = []
        self.__share_args__: list[ShareObjArgs] = []
        self.__share_cb_args__: list[ShareObjCbArgs] = []
        self.__hook_args__: list[BotHookRunnerArgs] = []

        self.__proxy__: PluginProxy

    def _self_build(self) -> None:
        self.__proxy__ = PluginProxy(
            self.__id__,
            self.__version__,
            self.__desc__,
            self.__pdoc__,
            self.__keywords__,
            self.__url__,
            [(args.namespace, args.id) for args in self.__share_args__],
            [(args.namespace, args.id) for args in self.__share_cb_args__],
            [(args.namespace, args.signal) for args in self.__signal_args__],
        )
        check_pass = all(
            False
            for pair in self.__proxy__.share_cbs
            if pair not in self.__proxy__.shares
        )
        if not check_pass:
            raise PluginInitError(
                f"插件 {self.__id__} 不能为不属于自己的共享对象注册回调"
            )

    def on_event(
        self,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """注册一个任意事件处理器

        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param session_rule: 会话规则，为空则不使用会话规则
        :param session_hold: 处理方法结束后是否保留会话（有会话规则才可启用）
        :param direct_rouse: 会话暂停时，是否允许不检查就唤醒会话（有会话规则才可启用）
        :param conflict_wait: 会话冲突时，是否需要事件等待处理（有会话规则才可启用）
        :param conflict_cb: 会话冲突时，运行的回调（有会话规则才可启用，`conflict_wait=True`，此参数无效）
        """

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
                    executor=executor,
                    type=AllEventHandler,
                    params=[
                        checker,
                        priority,
                        block,
                        temp,
                        session_rule,
                        session_hold,
                        direct_rouse,
                        conflict_wait,
                        conflict_cb,
                    ],
                )
            )
            return executor

        return make_args

    def on_message(
        self,
        matcher: Optional["BotMatcher"] = None,
        parser: Optional["BotParser"] = None,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """注册一个消息事件处理器

        :param matcher: 使用的匹配器（和解析器二选一）
        :param parser: 使用的解析器（和匹配器二选一）
        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param session_rule: 会话规则，为空则不使用会话规则
        :param session_hold: 处理方法结束后是否保留会话（有会话规则才可启用）
        :param direct_rouse: 会话暂停时，是否允许不检查就唤醒会话（有会话规则才可启用）
        :param conflict_wait: 会话冲突时，是否需要事件等待处理（有会话规则才可启用）
        :param conflict_cb: 会话冲突时，运行的回调（有会话规则才可启用，`conflict_wait=True`，此参数无效）
        """

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
                    executor=executor,
                    type=MsgEventHandler,
                    params=[
                        matcher,
                        parser,
                        checker,
                        priority,
                        block,
                        temp,
                        session_rule,
                        session_hold,
                        direct_rouse,
                        conflict_wait,
                        conflict_cb,
                    ],
                )
            )
            return executor

        return make_args

    def on_every_message(
        self,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """注册一个任意消息事件处理器

        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param session_rule: 会话规则，为空则不使用会话规则
        :param session_hold: 处理方法结束后是否保留会话（有会话规则才可启用）
        :param direct_rouse: 会话暂停时，是否允许不检查就唤醒会话（有会话规则才可启用）
        :param conflict_wait: 会话冲突时，是否需要事件等待处理（有会话规则才可启用）
        :param conflict_cb: 会话冲突时，运行的回调（有会话规则才可启用，`conflict_wait=True`，此参数无效）
        """

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
                    executor=executor,
                    type=MsgEventHandler,
                    params=[
                        None,
                        None,
                        checker,
                        priority,
                        block,
                        temp,
                        session_rule,
                        session_hold,
                        direct_rouse,
                        conflict_wait,
                        conflict_cb,
                    ],
                )
            )
            return executor

        return make_args

    def on_at_qq(
        self,
        qid: Optional[int] = None,
        matcher: Optional["BotMatcher"] = None,
        parser: Optional["BotParser"] = None,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """注册一个艾特消息事件处理器

        消息必须是艾特消息，且匹配成功才能被进一步处理。

        :param qid: 被艾特的 qq 号。为空则接受所有艾特消息;不为空则只接受指定 qid 被艾特的艾特消息
        :param matcher: 使用的匹配器（和解析器二选一）
        :param parser: 使用的解析器（和匹配器二选一）
        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param session_rule: 会话规则，为空则不使用会话规则
        :param session_hold: 处理方法结束后是否保留会话（有会话规则才可启用）
        :param direct_rouse: 会话暂停时，是否允许不检查就唤醒会话（有会话规则才可启用）
        :param conflict_wait: 会话冲突时，是否需要事件等待处理（有会话规则才可启用）
        :param conflict_cb: 会话冲突时，运行的回调（有会话规则才可启用，`conflict_wait=True`，此参数无效）
        """
        at_checker = AtChecker(qid)
        wrapped_checker: AtChecker | "WrappedChecker"
        if checker is not None:
            wrapped_checker = at_checker & checker
        else:
            wrapped_checker = at_checker

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
                    executor=executor,
                    type=MsgEventHandler,
                    params=[
                        matcher,
                        parser,
                        wrapped_checker,
                        priority,
                        block,
                        temp,
                        session_rule,
                        session_hold,
                        direct_rouse,
                        conflict_wait,
                        conflict_cb,
                    ],
                )
            )
            return executor

        return make_args

    def on_start_match(
        self,
        target: str | list[str],
        logic_mode: LogicMode = LogicMode.OR,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """注册一个字符串起始匹配的消息事件处理器

        `target` 为字符串时，只进行一次起始匹配，即判断是否匹配成功。
        `target` 为字符串列表时，所有字符串都进行起始匹配，再将所有结果使用给定
        `logic_mode` 计算是否匹配成功。

        消息必须匹配成功才能被进一步处理。

        :param target: 匹配目标
        :param logic_mode: `target` 为 `list[str]` 时的计算模式
        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param session_rule: 会话规则，为空则不使用会话规则
        :param session_hold: 处理方法结束后是否保留会话（有会话规则才可启用）
        :param direct_rouse: 会话暂停时，是否允许不检查就唤醒会话（有会话规则才可启用）
        :param conflict_wait: 会话冲突时，是否需要事件等待处理（有会话规则才可启用）
        :param conflict_cb: 会话冲突时，运行的回调（有会话规则才可启用，`conflict_wait=True`，此参数无效）
        """
        start_matcher = StartMatcher(target, logic_mode)

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
                    executor=executor,
                    type=MsgEventHandler,
                    params=[
                        start_matcher,
                        None,
                        checker,
                        priority,
                        block,
                        temp,
                        session_rule,
                        session_hold,
                        direct_rouse,
                        conflict_wait,
                        conflict_cb,
                    ],
                )
            )
            return executor

        return make_args

    def on_contain_match(
        self,
        target: str | list[str],
        logic_mode: LogicMode = LogicMode.OR,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """注册一个字符串包含匹配的消息事件处理器

        `target` 为字符串时，只进行一次包含匹配，即判断是否匹配成功。
        `target` 为字符串列表时，所有字符串都进行包含匹配，再将所有结果使用给定
        `logic_mode` 计算是否匹配成功。

        消息必须匹配成功才能被进一步处理。

        :param target: 匹配目标
        :param logic_mode: `target` 为 `list[str]` 时的计算模式
        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param session_rule: 会话规则，为空则不使用会话规则
        :param session_hold: 处理方法结束后是否保留会话（有会话规则才可启用）
        :param direct_rouse: 会话暂停时，是否允许不检查就唤醒会话（有会话规则才可启用）
        :param conflict_wait: 会话冲突时，是否需要事件等待处理（有会话规则才可启用）
        :param conflict_cb: 会话冲突时，运行的回调（有会话规则才可启用，`conflict_wait=True`，此参数无效）
        """
        contain_matcher = ContainMatcher(target, logic_mode)

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
                    executor=executor,
                    type=MsgEventHandler,
                    params=[
                        contain_matcher,
                        None,
                        checker,
                        priority,
                        block,
                        temp,
                        session_rule,
                        session_hold,
                        direct_rouse,
                        conflict_wait,
                        conflict_cb,
                    ],
                )
            )
            return executor

        return make_args

    def on_full_match(
        self,
        target: str | list[str],
        logic_mode: LogicMode = LogicMode.OR,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """注册一个字符串全匹配的消息事件处理器

        `target` 为字符串时，只进行一次全匹配，即判断是否匹配成功。
        `target` 为字符串列表时，所有字符串都进行全匹配，再将所有结果使用给定
        `logic_mode` 计算是否匹配成功。

        消息必须匹配成功才能被进一步处理。

        :param target: 匹配目标
        :param logic_mode: `target` 为 `list[str]` 时的计算模式
        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param session_rule: 会话规则，为空则不使用会话规则
        :param session_hold: 处理方法结束后是否保留会话（有会话规则才可启用）
        :param direct_rouse: 会话暂停时，是否允许不检查就唤醒会话（有会话规则才可启用）
        :param conflict_wait: 会话冲突时，是否需要事件等待处理（有会话规则才可启用）
        :param conflict_cb: 会话冲突时，运行的回调（有会话规则才可启用，`conflict_wait=True`，此参数无效）
        """
        full_matcher = FullMatcher(target, logic_mode)

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
                    executor=executor,
                    type=MsgEventHandler,
                    params=[
                        full_matcher,
                        None,
                        checker,
                        priority,
                        block,
                        temp,
                        session_rule,
                        session_hold,
                        direct_rouse,
                        conflict_wait,
                        conflict_cb,
                    ],
                )
            )
            return executor

        return make_args

    def on_end_match(
        self,
        target: str | list[str],
        logic_mode: LogicMode = LogicMode.OR,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """注册一个字符串结尾匹配的消息事件处理器

        `target` 为字符串时，只进行一次结尾匹配，即判断是否匹配成功。
        `target` 为字符串列表时，所有字符串都进行结尾匹配，再将所有结果使用给定
        `logic_mode` 计算是否匹配成功。

        消息必须匹配成功才能被进一步处理。

        :param target: 匹配目标
        :param logic_mode: `target` 为 `list[str]` 时的计算模式
        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param session_rule: 会话规则，为空则不使用会话规则
        :param session_hold: 处理方法结束后是否保留会话（有会话规则才可启用）
        :param direct_rouse: 会话暂停时，是否允许不检查就唤醒会话（有会话规则才可启用）
        :param conflict_wait: 会话冲突时，是否需要事件等待处理（有会话规则才可启用）
        :param conflict_cb: 会话冲突时，运行的回调（有会话规则才可启用，`conflict_wait=True`，此参数无效）
        """
        end_matcher = EndMatcher(target, logic_mode)

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
                    executor=executor,
                    type=MsgEventHandler,
                    params=[
                        end_matcher,
                        None,
                        checker,
                        priority,
                        block,
                        temp,
                        session_rule,
                        session_hold,
                        direct_rouse,
                        conflict_wait,
                        conflict_cb,
                    ],
                )
            )
            return executor

        return make_args

    def on_regex_match(
        self,
        target: str,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """注册一个字符串正则匹配的消息事件处理器

        消息必须匹配成功才能被进一步处理。

        :param target: 匹配目标的正则表达式，在匹配时，它应该可以使 :meth:`re.findall` 不返回空列表
        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param session_rule: 会话规则，为空则不使用会话规则
        :param session_hold: 处理方法结束后是否保留会话（有会话规则才可启用）
        :param direct_rouse: 会话暂停时，是否允许不检查就唤醒会话（有会话规则才可启用）
        :param conflict_wait: 会话冲突时，是否需要事件等待处理（有会话规则才可启用）
        :param conflict_cb: 会话冲突时，运行的回调（有会话规则才可启用，`conflict_wait=True`，此参数无效）
        """
        regex_matcher = RegexMatcher(target)

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
                    executor=executor,
                    type=MsgEventHandler,
                    params=[
                        regex_matcher,
                        None,
                        checker,
                        priority,
                        block,
                        temp,
                        session_rule,
                        session_hold,
                        direct_rouse,
                        conflict_wait,
                        conflict_cb,
                    ],
                )
            )
            return executor

        return make_args

    def on_request(
        self,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """注册一个请求事件处理器

        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param session_rule: 会话规则，为空则不使用会话规则
        :param session_hold: 处理方法结束后是否保留会话（有会话规则才可启用）
        :param direct_rouse: 会话暂停时，是否允许不检查就唤醒会话（有会话规则才可启用）
        :param conflict_wait: 会话冲突时，是否需要事件等待处理（有会话规则才可启用）
        :param conflict_cb: 会话冲突时，运行的回调（有会话规则才可启用，`conflict_wait=True`，此参数无效）
        """

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
                    executor=executor,
                    type=ReqEventHandler,
                    params=[
                        checker,
                        priority,
                        block,
                        temp,
                        session_rule,
                        session_hold,
                        direct_rouse,
                        conflict_wait,
                        conflict_cb,
                    ],
                )
            )
            return executor

        return make_args

    def on_friend_request(
        self,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """注册一个好友请求事件处理器

        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param session_rule: 会话规则，为空则不使用会话规则
        :param session_hold: 处理方法结束后是否保留会话（有会话规则才可启用）
        :param direct_rouse: 会话暂停时，是否允许不检查就唤醒会话（有会话规则才可启用）
        :param conflict_wait: 会话冲突时，是否需要事件等待处理（有会话规则才可启用）
        :param conflict_cb: 会话冲突时，运行的回调（有会话规则才可启用，`conflict_wait=True`，此参数无效）
        """
        friend_checker = FriendReqChecker()
        wrapped_checker: FriendReqChecker | "WrappedChecker"
        if checker is not None:
            wrapped_checker = friend_checker & checker
        else:
            wrapped_checker = friend_checker

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
                    executor=executor,
                    type=ReqEventHandler,
                    params=[
                        wrapped_checker,
                        priority,
                        block,
                        temp,
                        session_rule,
                        session_hold,
                        direct_rouse,
                        conflict_wait,
                        conflict_cb,
                    ],
                )
            )
            return executor

        return make_args

    def on_group_request(
        self,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """注册一个加群请求事件处理器

        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param session_rule: 会话规则，为空则不使用会话规则
        :param session_hold: 处理方法结束后是否保留会话（有会话规则才可启用）
        :param direct_rouse: 会话暂停时，是否允许不检查就唤醒会话（有会话规则才可启用）
        :param conflict_wait: 会话冲突时，是否需要事件等待处理（有会话规则才可启用）
        :param conflict_cb: 会话冲突时，运行的回调（有会话规则才可启用，`conflict_wait=True`，此参数无效）
        """
        group_checker = GroupReqChecker()
        wrapped_checker: GroupReqChecker | "WrappedChecker"
        if checker is not None:
            wrapped_checker = group_checker & checker
        else:
            wrapped_checker = group_checker

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
                    executor=executor,
                    type=ReqEventHandler,
                    params=[
                        wrapped_checker,
                        priority,
                        block,
                        temp,
                        session_rule,
                        session_hold,
                        direct_rouse,
                        conflict_wait,
                        conflict_cb,
                    ],
                )
            )
            return executor

        return make_args

    def on_notice(
        self,
        type: Literal[
            "group_upload",
            "group_admin",
            "group_decrease",
            "group_increase",
            "group_ban",
            "friend_add",
            "group_recall",
            "friend_recall",
            "group_card",
            "offline_file",
            "client_status",
            "essence",
            "notify",
            "honor",
            "poke",
            "lucky_king",
            "title",
            "ALL",
        ] = "ALL",
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """注册一个通知事件处理器

        :param type: 通知的类型，为 "ALL" 时接受所有通知
        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param session_rule: 会话规则，为空则不使用会话规则
        :param session_hold: 处理方法结束后是否保留会话（有会话规则才可启用）
        :param direct_rouse: 会话暂停时，是否允许不检查就唤醒会话（有会话规则才可启用）
        :param conflict_wait: 会话冲突时，是否需要事件等待处理（有会话规则才可启用）
        :param conflict_cb: 会话冲突时，运行的回调（有会话规则才可启用，`conflict_wait=True`，此参数无效）
        """
        type_checker = NoticeTypeChecker(type)
        wrapped_checker: NoticeTypeChecker | "WrappedChecker"
        if checker is not None:
            wrapped_checker = type_checker & checker
        else:
            wrapped_checker = type_checker

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
                    executor=executor,
                    type=NoticeEventHandler,
                    params=[
                        wrapped_checker,
                        priority,
                        block,
                        temp,
                        session_rule,
                        session_hold,
                        direct_rouse,
                        conflict_wait,
                        conflict_cb,
                    ],
                )
            )
            return executor

        return make_args

    def on_meta_event(
        self,
        checker: Optional["BotChecker"] = None,
        priority: PriorLevel = PriorLevel.MEAN,
        block: bool = False,
        temp: bool = False,
        session_rule: Optional["SessionRule"] = None,
        session_hold: bool = False,
        direct_rouse: bool = False,
        conflict_wait: bool = False,
        conflict_cb: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
    ):
        """注册一个元事件处理器

        :param checker: 使用的检查器，为空则默认通过检查
        :param priority: 优先级
        :param block: 是否进行优先级阻断
        :param temp: 是否是一次性的
        :param session_rule: 会话规则，为空则不使用会话规则
        :param session_hold: 处理方法结束后是否保留会话（有会话规则才可启用）
        :param direct_rouse: 会话暂停时，是否允许不检查就唤醒会话（有会话规则才可启用）
        :param conflict_wait: 会话冲突时，是否需要事件等待处理（有会话规则才可启用）
        :param conflict_cb: 会话冲突时，运行的回调（有会话规则才可启用，`conflict_wait=True`，此参数无效）
        """

        def make_args(
            executor: Callable[[], Coroutine[Any, Any, None]]
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            self.__handler_args__.append(
                EventHandlerArgs(
                    executor=executor,
                    type=MetaEventHandler,
                    params=[
                        checker,
                        priority,
                        block,
                        temp,
                        session_rule,
                        session_hold,
                        direct_rouse,
                        conflict_wait,
                        conflict_cb,
                    ],
                )
            )
            return executor

        return make_args

    def on_signal(self, namespace: str, signal: str):
        """注册一个信号处理方法

        本方法作为异步函数的装饰器使用，此时可注册一个函数为信号处理方法。

        .. code:: python

           # 假设存在一个名为 plugin 的变量，是 BotPlugin 实例
           # 为在命名空间 BaseUtils 中，名为 txt2img 的信号绑定处理方法：
           @plugin.on_signal("BaseUtils", "txt2img")
           async def get_img_of_txt(text: str, format: Any) -> bytes:
               # melobot 对被装饰函数的参数类型和返回值没有限制
               # 接下来是具体逻辑
               ...
           # 在这个示例中，具体的功能是为其他插件提供转换大段文本为图片的能力，因为大段文本不便于发送

        .. admonition:: 注意
           :class: caution

           在一个 bot 实例的范围内，同命名空间同名称的信号，只能注册一个处理方法。

        :param namespace: 信号的命名空间
        :param signal: 信号的名称
        """

        def make_args(
            func: Callable[P, Coroutine[Any, Any, Any]]
        ) -> Callable[P, Coroutine[Any, Any, Any]]:
            self.__signal_args__.append(
                PluginSignalHandlerArgs(func, namespace, signal)
            )
            return func

        return make_args

    def on_share(
        self, namespace: str, id: str, reflector: Optional[Callable[[], Any]] = None
    ):
        """注册一个共享对象，同时绑定它的值获取方法

        本方法可作为异步函数的装饰器使用，此时被装饰函数就是共享对象的值获取方法：

        .. code:: python

           # 假设存在一个名为 plugin 的变量，是 BotPlugin 实例
           # 在命名空间 HelpUtils 中，注册一个名为 all_helps 的共享对象，且绑定值获取方法：
           @plugin.on_share("HelpUtils", "all_helps")
           async def get_all_helps() -> str:
               # melobot 对被装饰函数的要求：无参数，但必须有返回值
               return ALL_HELPS_INFO_STR
           # 在这个示例中，具体的功能是在插件间共享 “所有插件的帮助文本” 这一数据

        当然，值获取方法较为简单时，直接传参即可：

        .. code:: python

           # 最后一个参数不能给定具体的值，必须为一个同步函数
           plugin.on_share("HelpUtils", "all_helps", lambda: ALL_HELPS_INFO_STR)

        .. admonition:: 注意
           :class: caution

           在一个 bot 实例的范围内，同命名空间同名称的共享对象，只能注册一个。

        :param namespace: 共享对象的命名空间
        :param id: 共享对象的 id 标识
        :param reflector: 为空时，本方法当作异步函数的装饰器使用；否则应该直接使用，此处提供共享对象值获取的反射函数
        """
        if reflector is not None:
            self.__share_args__.append(ShareObjArgs(namespace, id, to_async(reflector)))
            return

        def make_args(
            func: Callable[[], Coroutine[Any, Any, Any]]
        ) -> Callable[[], Coroutine[Any, Any, Any]]:
            self.__share_args__.append(ShareObjArgs(namespace, id, func))
            return func

        return make_args

    def on_share_affected(self, namespace: str, id: str):
        """为一个共享对象注册回调方法

        本方法作为异步函数的装饰器使用，此时可为一个共享对象注册回调方法。

        .. code:: python

           # 假设存在一个名为 plugin 的变量，是 BotPlugin 实例
           # 为在命名空间 HelpUtils 中，名为 all_helps 的共享对象绑定回调方法：
           @plugin.on_share_affected("HelpUtils", "all_helps")
           async def add_a_help(text: str) -> bool:
               # melobot 对被装饰函数的参数类型和返回值没有限制
               # 接下来是具体逻辑
               ...
           # 此回调用于被其他插件触发，为它们提供“影响”共享对象的能力，
           # 在这个示例中，具体的功能是让其他插件可以添加一条自己的帮助信息，但是有所校验

        .. admonition:: 注意
           :class: caution

           在一个 bot 实例的范围内，同命名空间同名称的共享对象，只能注册一个回调方法。
           而且这个共享对象必须在本插件通过 :meth:`on_share` 注册（共享对象注册、共享对象回调注册先后顺序不重要）

        :param namespace: 共享对象的命名空间
        :param id: 共享对象的 id 标识
        """

        def make_args(
            func: Callable[P, Coroutine[Any, Any, Any]]
        ) -> Callable[P, Coroutine[Any, Any, Any]]:
            self.__share_cb_args__.append(ShareObjCbArgs(namespace, id, func))
            return func

        return make_args

    def on_bot_life(self, type: BotLife):
        """注册 bot 在某个生命周期的 hook 方法

        本方法作为异步函数的装饰器使用，此时可注册一个函数为 bot 生命周期 hook 方法。

        .. code:: python

           # 假设存在一个名为 plugin 的变量，是 BotPlugin 实例
           # 我们希望这个插件，在 bot 连接器建立连接后给某人发一条消息
           @plugin.on_bot_life(BotLife.CONNECTED)
           async def say_hi() -> None:
               # melobot 对被装饰函数的要求：无参数，返回空值
               await send_custom_msg("Hello~", isPrivate=True, userId=xxxxx)
           # 在这个示例中，bot 登录上号后，便会向 xxxxx 发送一条 Hello~ 消息

        :param type: bot 生命周期类型枚举值
        """

        def make_args(
            func: Callable[P, Coroutine[Any, Any, None]]
        ) -> Callable[P, Coroutine[Any, Any, None]]:
            self.__hook_args__.append(BotHookRunnerArgs(func, type))
            return func

        return make_args

    @property
    def on_plugins_loaded(self):
        """注册 bot 在 :attr:`.BotLife.LOADED` 生命周期的 hook 方法

        本方法作为异步函数的装饰器使用。用法与 :class:`on_bot_life` 类似。
        """
        return self.on_bot_life(BotLife.LOADED)

    @property
    def on_connected(self):
        """注册 bot 在 :attr:`.BotLife.CONNECTED` 生命周期的 hook 方法

        本方法作为异步函数的装饰器使用。用法与 :class:`on_bot_life` 类似。
        """
        return self.on_bot_life(BotLife.CONNECTED)

    @property
    def on_before_close(self):
        """注册 bot 在 :attr:`.BotLife.BEFORE_CLOSE` 生命周期的 hook 方法

        本方法作为异步函数的装饰器使用。用法与 :class:`on_bot_life` 类似。
        """
        return self.on_bot_life(BotLife.BEFORE_CLOSE)

    @property
    def on_before_stop(self):
        """注册 bot 在 :attr:`.BotLife.BEFORE_STOP` 生命周期的 hook 方法

        本方法作为异步函数的装饰器使用。用法与 :class:`on_bot_life` 类似。
        """
        return self.on_bot_life(BotLife.BEFORE_STOP)

    @property
    def on_event_built(self):
        """注册 bot 在 :attr:`.BotLife.EVENT_BUILT` 生命周期的 hook 方法

        本方法作为异步函数的装饰器使用。用法与 :class:`on_bot_life` 类似。
        """
        return self.on_bot_life(BotLife.EVENT_BUILT)

    @property
    def on_action_presend(self):
        """注册 bot 在 :attr:`.BotLife.ACTION_PRESEND` 生命周期的 hook 方法

        本方法作为异步函数的装饰器使用。用法与 :class:`on_bot_life` 类似。
        """
        return self.on_bot_life(BotLife.ACTION_PRESEND)
