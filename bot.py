import nonebot
from nonebot.adapters.onebot.v11 import Adapter as Onebotv11Adapter


nonebot.init()
driver = nonebot.get_driver()
driver.register_adapter(Onebotv11Adapter)
nonebot.load_from_toml("pyproject.toml")



if __name__ == "__main__":
    nonebot.run()
