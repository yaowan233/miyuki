import nonebot
from nonebot.adapters.satori import Adapter as SATORIAdapter



nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(SATORIAdapter)

nonebot.load_builtin_plugins('echo')


nonebot.load_from_toml("pyproject.toml")

if __name__ == "__main__":
    nonebot.run()