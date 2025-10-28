# -*- coding: utf-8 -*-
"""PyNCM_Async 网易云音乐 Python 异步 API / 下载工具

PyNCM_Async 包装的网易云音乐 API 的使用非常简单::

    >>> import asyncio
    >>> import pyncm_async
    >>> async def main():
    >>>     session = pyncm_async.Session()
    >>>     # 获取歌曲信息
    >>>     await pyncm_async.apis.track.GetTrackAudio(29732235, session=session)
    >>>     # 获取歌曲详情
    >>>     await pyncm_async.apis.track.GetTrackDetail(29732235, session=session)
    >>>     # 获取歌曲评论
    >>>     await pyncm_async.apis.track.GetTrackComments(29732235, session=session)
    >>> asyncio.run(main())

PyNCM_Async 的所有 API 请求都将经过传入的 `pyncm_asycn.Session` 发出，调用时必须显式传入 `session` 参数:

    >>> session = Session
    >>> await pyncm_async.apis.track.GetTrackComments(29732235, session=session)

PyNCM_Async 提供了相应的 Session 序列化函数，用于其储存及管理::

    >>> session_str = pyncm_asycn.DumpSessionAsString(session)
    >>> new_session = pyncm_asycn.LoadSessionFromString(session_str)

# 注意事项
    - (PR#11) 海外用户可能经历 460 "Cheating" 问题，可通过添加以下 Header 解决: `X-Real-IP = 118.88.88.88`
"""

__VERSION_MAJOR__ = 1
__VERSION_MINOR__ = 8
__VERSION_PATCH__ = 2

__version__ = f"{__VERSION_MAJOR__}.{__VERSION_MINOR__}.{__VERSION_PATCH__}"

from asyncio import get_running_loop
from typing import Text, Union
from time import time

from .utils import GenerateSDeviceId, GenerateWNMCID
from .utils.crypto import EapiEncrypt, EapiDecrypt, HexCompose
import httpx, logging, json, os

logger = logging.getLogger("pyncm_asycn.api")
if "PYNCM_ASYNC_DEBUG" in os.environ:
    debug_level = os.environ["PYNCM_ASYNC_DEBUG"].upper()
    if not debug_level in {"CRITICAL", "DEBUG", "ERROR", "FATAL", "INFO", "WARNING"}:
        debug_level = "DEBUG"
    logging.basicConfig(
        level=debug_level, format="[%(levelname).4s] %(name)s %(message)s"
    )

# 默认 deviceID
# This sometimes fails with some strings, for no particular reason. Though `pyncm!` seem to work everytime..?
# Though with this, all pyncm users would then be sharing the same device Id.
# Don't think that would be of any issue though...
DEVICE_ID_DEFAULT = "pyncm!"


class Session(httpx.AsyncClient):
    """# Session
        实现网易云音乐登录态 / API 请求管理

        - HTTP方面，`Session`的配置方法和 `httpx.AsyncClient` 完全一致，如配置 Headers:

        Session().headers['X-Real-IP'] = '1.1.1.1'

        - 该 Session 其他参数也可被修改:

        Session().force_http = True # 优先 HTTP

        获取其他具体信息请参考该文档注释
    """

    HOST = "music.163.com"
    """网易云音乐 API 服务器域名，可直接改为代理服务器之域名"""
    UA_DEFAULT = (
        f"Mozilla/5.0 (linux@github.com/mos9527/pyncm_asycn) Chrome/PyNCM_Async.{__version__}"
    )
    """Weapi 使用的 UA"""
    UA_EAPI = "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36 Chrome/91.0.4472.164 NeteaseMusicDesktop/2.10.2.200154"
    """EAPI 使用的 UA，不推荐更改"""
    UA_LINUX_API = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.90 Safari/537.36"
    """曾经的 Linux 客户端 UA，不推荐更改"""
    force_http = False
    """优先使用 HTTP 作 API 请求协议"""

    async def __aenter__(self) -> httpx.AsyncClient:
        raise TypeError(
            f"{self.__class__.__name__} does not support the context manager"
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": self.UA_DEFAULT,
            "Referer": self.HOST,
        }
        self.login_info = {"success": False, "tick": time(), "content": None}
        # https://gitlab.com/Binaryify/neteasecloudmusicapi/-/blob/main/util/request.js?ref_type=heads
        self.eapi_config = {
            "os": "iPhone OS",
            "appver": "10.0.0",
            "osver": "16.2",
            "channel": "distribution",
            "deviceId": DEVICE_ID_DEFAULT,
        }
        self.weapi_config = {
            "WEVNSM": "1.0.0",
            "sDeviceId": GenerateSDeviceId(),
            "WNMCID": GenerateWNMCID(),
        }
        self.csrf_token = ""

    # region Shorthands
    @property
    def deviceId(self):
        """设备 ID"""
        return self.eapi_config["deviceId"]

    @deviceId.setter
    def deviceId(self, value: str):
        self.eapi_config["deviceId"] = value

    @property
    def sDeviceId(self):
        return self.weapi_config["sDeviceId"]

    @sDeviceId.setter
    def sDeviceId(self, value: str):
        self.weapi_config["sDeviceId"] = value

    @property
    def uid(self):
        """用户 ID"""
        return self.login_info["content"]["account"]["id"] if self.logged_in else 0

    @property
    def nickname(self):
        """登陆用户的昵称"""
        return (
            self.login_info["content"]["profile"]["nickname"] if self.logged_in else ""
        )

    @property
    def lastIP(self):
        """登陆时，上一次登陆的 IP"""
        return (
            self.login_info["content"]["profile"]["lastLoginIP"]
            if self.logged_in
            else ""
        )

    @property
    def vipType(self):
        """账号 VIP 等级"""
        return (
            self.login_info["content"]["profile"]["vipType"]
            if self.logged_in and not self.is_anonymous
            else 0
        )

    @property
    def logged_in(self):
        """是否已经登陆"""
        return self.login_info["success"]

    @property
    def is_anonymous(self):
        """是否匿名登陆"""
        return self.logged_in and not self.nickname

    # endregion
    async def request(
        self, method: str, url: Union[str, bytes, Text], *args, **kwargs
    ) -> httpx.Response:
        """发起 HTTP(S) 请求
        该函数与 ` -> httpx.AsyncClient.request` 有以下不同：
        - 使用 SSL 与否取决于 `force_http`
        - 不强调协议（只用 HTTP(S)），不带协议的链接会自动补上 HTTP(S)

        Args:
            method (str): HTTP Verb
            url (Union[str, bytes, Text]): Complete/Partial HTTP URL

        Returns:
            httpx.Response
        """
        if url[:4] != "http":
            url = f"https://{self.HOST}{url}"
        if self.force_http:
            url = url.replace("https:", "http:")
        return await super().request(method, url, *args, **kwargs)

    # region symbols for loading/reloading authentication info
    _session_info = {
        "eapi_config": (
            lambda self: getattr(self, "eapi_config"),
            lambda self, v: setattr(self, "eapi_config", v),
        ),
        "weapi_config": (
            lambda self: getattr(self, "weapi_config"),
            lambda self, v: setattr(self, "weapi_config", v),
        ),
        "login_info": (
            lambda self: getattr(self, "login_info"),
            lambda self, v: setattr(self, "login_info", v),
        ),
        "csrf_token": (
            lambda self: getattr(self, "csrf_token"),
            lambda self, v: setattr(self, "csrf_token", v),
        ),
        "cookies": (
            lambda self: [
                {"name": c.name, "value": c.value, "domain": c.domain, "path": c.path}
                for c in getattr(getattr(self, "cookies"), "jar")
            ],
            lambda self, cookies: [
                getattr(self, "cookies").set(**cookie) for cookie in cookies
            ],
        ),
    }

    def dump(self) -> dict:
        """以 `dict` 导出登录态"""
        return {
            name: self._session_info[name][0](self)
            for name in self._session_info.keys()
        }

    def load(self, dumped):
        """从 `dict` 加载登录态"""
        for k, v in dumped.items():
            self._session_info[k][1](self, v)
        return True
    
    # endregion


class SessionManager:
    """PyNCM_Async Session 单例储存对象"""

    # region Session serialization
    @staticmethod
    def stringify_legacy(session: Session) -> str:
        """（旧）序列化 `Session` 为 `str`"""
        return EapiEncrypt("pyncm", json.dumps(session.dump()))["params"]

    @staticmethod
    def parse_legacy(dump: str) -> Session:
        """（旧）反序列化 `str` 为 `Session`"""
        session = Session()
        dump = HexCompose(dump)
        dump = EapiDecrypt(dump).decode()
        dump = dump.split("-36cd479b6b5-")
        assert dump[0] == "pyncm"  # check magic
        session.load(json.loads(dump[1]))  # loading config dict
        return session

    @staticmethod
    def stringify(session: Session) -> str:
        """序列化 `Session` 为 `str`"""
        from json import dumps
        from zlib import compress
        from base64 import b64encode

        return "PYNCM" + b64encode(compress(dumps(session.dump()).encode())).decode()

    @staticmethod
    def parse(dump: str) -> Session:
        """反序列化 `str` 为 `Session`"""
        if (
            dump[:5] == "PYNCM"
        ):  # New marshaler (compressed,base64 encoded) has magic header
            from json import loads
            from zlib import decompress
            from base64 import b64decode

            session = Session()
            session.load(loads(decompress(b64decode(dump[5:])).decode()))
            return session
        else:
            return SessionManager.parse_legacy(dump)


# endregion

sessionManager = SessionManager()


def LoadSessionFromString(dump: str) -> Session:
    """从 `str` 加载 Session / 登录态"""
    session = SessionManager.parse(dump)
    return session


def DumpSessionAsString(session: Session) -> str:
    """从 Session / 登录态 导出 `str`"""
    return SessionManager.stringify(session)


def WriteLoginInfo(content: dict, session: Session):
    """写登录态入Session

    Args:
        content (dict): 解码后的登录态
        session (Session)

    Raises:
        LoginFailedException: 登陆失败时发生
    """

    session.login_info = {"tick": time(), "content": content}
    if not session.login_info["content"]["code"] == 200:
        session.login_info["success"] = False
        raise Exception(session.login_info["content"])
    session.login_info["success"] = True
    session.csrf_token = session.cookies.get("__csrf")
