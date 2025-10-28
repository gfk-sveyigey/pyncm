# PyNCM Async

[![PyPI version](https://badge.fury.io/py/pyncm-async.svg)](https://badge.fury.io/py/pyncm-async)


提供异步支持的第三方 Python 网易云音乐 API

**注意** : 同步使用，请移步 [`master` 分支](https://github.com/mos9527/pyncm/tree/master)

# **注意：长期支持状态** 
上游 API 变更、BUG 修复、安全更新等**有可能**得到及时响应；Feature Request 及非紧急 Issues 将被延后处理或不处理。

有意维护者请通过 GitHub Issues 联系获得 Collaborator 权限（不保证通过），或通过 Pull Request 贡献更改。

# 安装
    pip install pyncm-async

# API 使用示例
```python
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
```

## Session
`Session` 继承自 `httpx.AsyncClient`，用于异步执行网络请求。

自 `Version 2.0.0` 开始，`pyncm_async` 不再对 `Session` 进行管理，使用上存在以下不同：

- 需要自行管理 `Session`，以及处理异步安全相关问题；

- 在调用 API 时必须显式传入 `session` 参数；

- `Session` 不再支持作为上下文管理器使用；

- `CurrentSession` 相关的函数已被移除，但仍可通过 `LoadSessionFromString` 创建或直接实例化 `Session`。

## API 说明
大部分 API 函数已经详细注释，可读性较高。推荐参阅 [API 源码](https://github.com/mos9527/pyncm/tree/async/pyncm_async) 获得支持

## 添加新API
`pyncm_async` 仅封装了常用且相对稳定的 API。如果需要使用更多 API，可以自行添加。

在添加新 API 时，需要明确以下5项内容：
- 是否返回原始响应内容
- API 来源  --Weapi/Eapi
- API 路径
- 请求参数  --必须为 `dict` 类型，即使无参数也需传入空字典 __{}__
- 请求方法  --默认为 `POST`，可空

如果返回原始响应内容，可以直接使用 `pyncm_async`提供的装饰器对 API 进行装饰，并遵循以下规范：
- API 须定义为 __同步__ 函数 (仍以异步调用，由装饰器实现)；
- API  __不应包含__ 关键字参数 `session` (调用时需显式传入该参数，由装饰器实现)；
- __不应标注__ 返回值类型 (返回`dict`， 由装饰器实现)。
```python
@WeapiCryptoRequest
def new_api(*args, **kwargs):
    path: str
    params: dict
    method: str
    ...
    return path, params, method
```
如需要对原始响应内容进行处理，可利用匿名函数 `lambda` 来实现，并遵循以下规范：
- API 须定义为 __异步__ 函数；
- API  __须包含__ 关键字参数 `session`；
- 返回字典类型的结果。
```python
async def new_api(*args,  session: Session, **kwargs) -> dict:
    api_func = lambda : (path, params, method)
    request_func = EapiCryptoRequest(api_fnc)
    res = await request_func(session=session)
    ...
```

# 感谢
[Android逆向——网易云音乐排行榜api(上)](https://juejin.im/post/6844903586879520775)

[Binaryify/NeteaseCloudMusicApi](https://github.com/Binaryify/NeteaseCloudMusicApi)
