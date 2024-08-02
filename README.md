# miyuki
miyuki大部分插件都使用了 [nonebot_plugin_alconna](https://github.com/nonebot/plugin-alconna) 进行消息发送，理论上支持大部分适配器，你可以根据需求，[自行选择适配器](https://nonebot.dev/store/adapters)


## 启动步骤

1. [安装 python](https://www.python.org/downloads/)
2. [安装 pdm](https://pdm-project.org/en/latest/#__tabbed_1_1)
3. 安装依赖 `pdm install`
4. 升级数据库 `pdm run nb orm upgrade` (第一次启动需要)
5. 启动 bot `pdm run nb run`

## 使用 docker
1. `docker build .`
2. `docker run <image>`

## 官方文档

See [Docs](https://nonebot.dev/)
