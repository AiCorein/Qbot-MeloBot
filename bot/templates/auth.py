from core.Executor import EXEC, AuthRole
from common import *
from common.Action import msg_action


@EXEC.template(
    aliases=['权限'], 
    userLevel=AuthRole.USER, 
    comment='权限检查',
    prompt='无参数'
)
async def auth(session: BotSession) -> None:
    event = session.event
    u_lvl = EXEC.msg_checker.get_event_lvl(event)

    if event.msg.is_group():
        u_nickname = event.msg.sender.group_card
        if u_nickname == '':
            u_nickname = event.msg.sender.nickname
    elif event.msg.is_private():
        u_nickname = event.msg.sender.nickname

    alist = [
        u_nickname,
        BOT_STORE.config.bot_name,
        u_lvl >= AuthRole.OWNER,
        u_lvl >= AuthRole.SU,
        u_lvl >= AuthRole.WHITE,
        u_lvl >= AuthRole.USER,
    ]

    auth_str = "{} 对 {} 拥有权限：\
    \nowner：{}\nsuperuser：{}\nwhite：{}\nuser：{}".format(*alist)

    await session.send(auth_str)