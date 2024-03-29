:tocdepth: 3

melobot.utils
=============

日志器
-------

日志器可自行实例化，也可直接通过 :attr:`.thisbot.logger` 获取当前 bot 实例的日志器。

.. autoclass:: melobot.utils.BotLogger
   :members:
   :show-inheritance:

匹配器
---------------

匹配器被用于消息事件处理的文本匹配过程。

.. admonition:: 相关知识
   :class: seealso

   对于消息事件处理器来说，预处理过程主要分为三步：匹配或解析、检查和格式化。

   但对于其他事件处理器来说，预处理过程只有一步：检查。

.. autoclass:: melobot.utils.StartMatcher
   :members:
   :show-inheritance:
   :exclude-members: match

.. autoclass:: melobot.utils.ContainMatcher
   :members:
   :show-inheritance:
   :exclude-members: match

.. autoclass:: melobot.utils.EndMatcher
   :members:
   :show-inheritance:
   :exclude-members: match

.. autoclass:: melobot.utils.FullMatcher
   :members:
   :show-inheritance:
   :exclude-members: match

.. autoclass:: melobot.utils.RegexMatcher
   :members:
   :show-inheritance:
   :exclude-members: match

检查器
---------------

检查器被用于所有事件处理的事件检查。

.. admonition:: 相关知识
   :class: seealso

   对于消息事件处理器来说，预处理过程主要分为三步：匹配或解析、检查和格式化。
   
   但对于其他事件处理器来说，预处理过程只有一步：检查。

.. autoclass:: melobot.utils.MsgLvlChecker
   :members:
   :show-inheritance:
   :exclude-members: check

.. autoclass:: melobot.utils.GroupMsgLvlChecker
   :members:
   :show-inheritance:
   :exclude-members: check

.. autoclass:: melobot.utils.PrivateMsgLvlChecker
   :members:
   :show-inheritance:
   :exclude-members: check

.. autoclass:: melobot.utils.MsgCheckerGen
   :members:

.. autoclass:: melobot.utils.AtChecker
   :members:
   :show-inheritance:
   :exclude-members: check

.. autoclass:: melobot.utils.FriendReqChecker
   :members:
   :show-inheritance:
   :exclude-members: check

.. autoclass:: melobot.utils.GroupReqChecker
   :members:
   :show-inheritance:
   :exclude-members: check

.. autoclass:: melobot.utils.NoticeTypeChecker
   :members:
   :show-inheritance:
   :exclude-members: check


解析器
---------------

解析器被用于消息事件处理的命令参数解析过程。

.. admonition:: 相关知识
   :class: seealso

   对于消息事件处理器来说，预处理过程主要分为三步：匹配或解析、检查和格式化。
   
   但对于其他事件处理器来说，预处理过程只有一步：检查。

.. autoclass:: melobot.utils.CmdParser
   :members:

.. autoclass:: melobot.utils.CmdParserGen
   :members:

格式化器
----------------

格式化器被用于消息事件处理的命令参数格式化过程。

.. admonition:: 相关知识
   :class: seealso

   对于消息事件处理器来说，预处理过程主要分为三步：匹配或解析、检查和格式化。
   
   但对于其他事件处理器来说，预处理过程只有一步：检查。

.. autoclass:: melobot.utils.ArgFormatter
   :members:

.. autoclass:: melobot.utils.FormatInfo
   :members:
   :exclude-members: __init__
