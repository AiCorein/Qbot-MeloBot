from .globalPattern import *
from .botLogger import BOT_LOGGER
from abc import abstractclassmethod, ABC
from typing import Literal, List, Union
from copy import deepcopy
import time as t


class CQEncoder(Singleton):
    """
    CQ 格式编码器，调用指定方法，即可获得对应的 CQ 消息，
    输出支持 dict 和字符串格式。
    """
    def __init__(self) -> None:
        super().__init__()

    def escape(self, text: str) -> str:
        """
        cq 字符转义
        """
        return text.replace('&', '&amp;')\
                    .replace('[', '&#91;')\
                    .replace(']', '&#93;')\
                    .replace(',', '&#44;')

    def anti_escape(self, text: str) -> str:
        """
        cq 字符逆转义
        """
        return text.replace('&amp;', '&')\
                    .replace('&#91;', '[')\
                    .replace('&#93;', ']')\
                    .replace('&#44;', ',')
    
    def text(self, text: str, fromEvent: bool=True, mode: Literal["str", "dict"]="str"):
        """
        普通文本消息。
        注意字符串如果是来自事件中的，则不需要转义，因为 cq 传给 bot 时已经转义。
        但如果是来自 bot 内部的，最好转义。
        """
        if mode == "str":
            if fromEvent: return text
            else: return text.replace('&', '&amp;')\
                    .replace('[', '&#91;')\
                    .replace(']', '&#93;')
        return {
            "type": "text",
            "data": {
                "text": text,
            }
        }

    def face(self, icon_id: int, mode: Literal["str", "dict"]="str"):
        """
        QQ 表情
        """
        if mode == "str":
            return f"[CQ:face,id={icon_id}]"
        else: 
            return {
                "type": "face",
                "data": {
                    "id": f"{icon_id}"
                }
            }
    
    def record(self, url: str, timeout: int=None, 
                magic: bool=False, mode: Literal["str", "dict"]="str"):
        """
        语音消息
        """
        if mode == "str": 
            url = self.escape(url)
            base = f"[CQ:record,file={url}"
            if magic: base += ',magic=1'
            if timeout: base += f',timeout={timeout}'
            base += ']'
            return base
        else:
            base =  {
                "type": "record",
                "data": {
                    "file": url,
                }
            }
            if magic: base['data']['magic'] = 1
            if timeout: base['data']['timeout'] = timeout
            return base

    def at(self, qq:Union[int ,Literal['all']], notInName: str=None, 
            mode: Literal["str", "dict"]="str"):
        """
        at 消息。
        at 所有人时，qq 传 "all"
        """
        if mode == "str": 
            if notInName: notInName = self.escape(notInName)
            base =  f"[CQ:at,qq={qq}"
            if notInName: base += ',name={notInName}'
            base += ']'
            return base
        else:
            base = {
                "type": "at",
                "data": {
                    "qq": qq,
                }
            }
            if notInName: base['data']['name'] = notInName
            return base

    def share(self, url: str, title: str, content: str=None, 
                image: str=None, mode: Literal["str", "dict"]="str"):
        """
        链接分享卡片消息。
        content 为描述语
        """
        if mode == "str": 
            url = self.escape(url)
            title = self.escape(title)
            if content: content = self.escape(content)
            if image: image = self.escape(image)

            base = f"[CQ:share,url={url},title={title}"
            if content: base += f',content={content}'
            if image: base += f',image={image}'
            base += ']'
            return base
        else:
            base = {
                "type": "share",
                "data": {
                    "url": url,
                    "title": title,
                }
            }
            if content: base['data']['content'] = content
            if image: base['data']['image'] = image
            return base
    

    def music(self, platType: Literal["qq", "163", "xm"],
                songId: str, mode: Literal["str", "dict"]="str"):
        """
        音乐分享卡片消息（专有平台）
        """
        if mode == "str":
            return f"[CQ:music,type={platType},id={songId}]"
        else:
            return {
                "type": "music",
                "data": {
                    "type": platType,
                    "id": songId
                }
            }
    
    def custom_music(self, url: str, audio: str, title: str, 
                        content: str=None, image: str=None, 
                        mode: Literal["str", "dict"]="str"):
        """
        自定义音乐分享卡片。
        url 为主页或网站起始页
        """
        if mode == "str": 
            url = self.escape(url)
            audio = self.escape(audio)
            title = self.escape(title)
            if content: content = self.escape(content)
            if image: image = self.escape(image)

            base = f"[CQ:music,type=custom,url={url},audio={audio},title={title}"
            if content: base += f',content={content}'
            if image: base += f',image={image}'
            base += ']'
            return base
        else:
            base = {
                "type": "music",
                "data": {
                    "type": "custom",
                    "url": url,
                    "audio": audio,
                    "title": title,
                }
            }
            if content: base['data']['content'] = content
            if image: base['data']['image'] = image
            return base
    
    def image(self, file: str, picType: Literal["flash", "show"]=None, 
                subType: Literal[0, 1]=None, cache: Literal[0, 1]=1,
                mode: Literal["str", "dict"]="str"):
        """
        图片消息。
        picType flash 为闪照，show 为秀图，不填为普通图片。
        subType 只出现在群聊，0 为正常图片，1 为表情包
        """
        if mode == "str":
            file = self.escape(file)
            base = f"[CQ:image,file={file}"
            if picType: base += f",type={picType}"
            if subType: base += f",subType={subType}"
            if cache: base += f",cache={cache}"
            base += ']'
            return base
        else:
            base = {
                "type": "image",
                "data": {
                    "file": file,
                }
            }
            if picType: base['data']['type'] = picType
            if subType: base['data']['subType'] = subType
            if cache: base['data']['cache'] = cache
            return base
    
    def reply(self, messageId: int, mode: Literal["str", "dict"]="str"):
        """
        回复消息
        """
        if mode == "str":
            return f"[CQ:reply,id={messageId}]"
        else:
            return {
                "type": "reply",
                "data": {
                    "id": messageId,
                }
            }

    def poke(self, qqId: int, mode: Literal["str", "dict"]="str"):
        """
        戳一戳消息
        """
        if mode == "str":
            return f"[CQ:poke,qq={qqId}]"
        else:
            return {
                "type": "poke",
                "data": {
                    "qq": qqId,
                }
            }
    
    def tts(self, text: str, mode: Literal["str", "dict"]="str"):
        """
        腾讯自带 tts 语音消息
        """
        if mode == "str":
            text = self.escape(text)
            return f"[CQ:tts,text={text}]"
        else:
            return {
                "type": "tts",
                "data": {
                    "text": text,
                }
            }


class ActionPacker(Singleton, ABC):
    """
    action params 封装器基类，这里命令为 action packer。
    主要负责封装 action 复杂的 params dict 和 action_type
    """
    def __init__(self) -> None:
        super().__init__()
        self.__package = {
            "action_type": "",
            "params": {}
        }

    @abstractclassmethod
    def pack(self) -> dict:
        """
        所有子类应该实现 pack 方法
        """
        pass


class MsgSendPacker(ActionPacker, Singleton):
    """
    发送消息 action packer
    """
    def __init__(self) -> None:
        super().__init__()
        self.__package = {
            "action_type": "",
            "params": {}
        }
    
    def private_pack(self, cqEncodeMsgs: List[Union[str, dict]], 
                userId: int, isPureText: bool=False) -> dict:
        """
        私聊消息包装

        isPureText 为假，则告诉 cq 自动解析字符串中的 CQ 格式字符串。
        一般除特殊情况，不推荐设置为 True。
        """
        packed = self.__package.copy()
        packed['action_type'] = 'send_private_msg'
        if isinstance(cqEncodeMsgs[0], str):
            packed['params']['message'] = ''.join(cqEncodeMsgs)
        else:
            packed['params']['message'] = cqEncodeMsgs
        if isPureText: packed['params']['auto_escape'] = True
        packed['params']['user_id'] = userId
        return packed
    
    def group_pack(self, cqEncodeMsgs: List[Union[str, dict]], 
                groupId: int, isPureText: bool=False) -> dict:
        """
        群聊消息包装

        isPureText 为假，则告诉 cq 自动解析字符串中的 CQ 格式字符串。
        一般除特殊情况，不推荐设置为 True。
        """
        packed = self.__package.copy()
        packed['action_type'] = 'send_group_msg'
        if isinstance(cqEncodeMsgs[0], str):
            packed['params']['message'] = ''.join(cqEncodeMsgs)
        else:
            packed['params']['message'] = cqEncodeMsgs
        if isPureText: packed['params']['auto_escape'] = True
        packed['params']['group_id'] = groupId
        return packed

    def pack(self, event: dict, cqEncodeMsgs: List[Union[str, dict]], 
                isPureText: bool=False) -> dict:
        """
        消息包装，根据 event 自动判断应该发送何种消息

        isPureText 为假，则告诉 cq 自动解析字符串中的 CQ 格式字符串。
        一般除特殊情况，不推荐设置为 True。
        """
        packed = {}
        if event['post_type'] == 'message' in event.keys() and event['message_type'] == 'group':
            packed =  self.group_pack(cqEncodeMsgs, event['group_id'], isPureText)
        elif event['post_type'] == 'message' and event['message_type'] == 'private':
            packed = self.private_pack(cqEncodeMsgs, event['user_id'], isPureText)
        elif event['post_type'] == 'notice' and event['sub_type'] == 'poke':
            if 'group_id' in event:
                packed = self.group_pack(cqEncodeMsgs, event['group_id'], isPureText)
            else:
                packed = self.private_pack(cqEncodeMsgs, event['user_id'], isPureText)
        else:
            BOT_LOGGER.error(f"消息 action 封装错误，事件 {event} 不合法！")
            raise BotUnexpectedEvent("预期之外的 event 事件")
        return packed



class MsgDelPacker(ActionPacker, Singleton):
    """
    撤回消息 action packer
    """
    def __init__(self) -> None:
        super().__init__()
        self.__package = {
            "action_type": "",
            "params": {}
        }
    
    def pack(self, msgId: int):
        """
        撤回消息包装，传入 message id 以获取消息信息
        """
        packed = self.__package.copy()
        packed['action_type'] = 'delete_msg'
        packed['params']['message_id'] = msgId
        return packed


class GetLoginfoPacker(ActionPacker, Singleton):
    """
    获取 bot 号信息 action packer
    """
    def __init__(self) -> None:
        super().__init__()
        self.__package = {
            "action_type": "",
            "params": {}
        }

    def pack(self):
        """
        无需参数，用于查询 bot id 和昵称
        """
        packed = self.__package.copy()
        packed['action_type'] = 'get_login_info'
        return packed


class ActionBuilder(Singleton):
    """
    action 对象构造类，构造各类 action 对象
    """
    def __init__(self) -> None:
        super().__init__()
        self.__resp = {
            "action": "",
            "params": {},
        }

    def build(self, package: dict, isEcho=False) -> dict:
        """
        build 一个 action 对象。

        isEcho 参数用于指定该 action 响应后， cq 是否在响应 event 附加上 echo 唯一标识符，
        以用于区分响应事件。此处 isEcho 若为真，会自动使用纳秒时间戳作为唯一标识符。
        """
        # 以毫秒时间戳作为 echo 的唯一标识
        resp = self.__resp.copy()
        if isEcho: resp['echo'] = int(t.time()*1000000)
        resp['action'] = package['action_type']
        resp['params'] = package['params']
        # 一定要 deepcopy，因为这里的类是单例，不拷贝多个 action 将会交叉引用！
        return deepcopy(resp)


Builder = ActionBuilder()
Encoder = CQEncoder()
msg_del_packer = MsgDelPacker()
msg_send_packer = MsgSendPacker()