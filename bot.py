from os import environ

from nonebot import get_asgi, get_driver, init, load_plugins, run
from nonebot.adapters.console import Adapter as CAdapter
from nonebot.adapters.onebot.v11 import Adapter as ObAdapter

init()
app = get_asgi()
driver = get_driver()
if environ.get("TEST"):
    driver.register_adapter(CAdapter)
else:
    driver.register_adapter(ObAdapter)
load_plugins("agibot/plugins")
run()
