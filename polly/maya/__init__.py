import os

from mindbender import api as mindbender
from pyblish import api as pyblish

from . import menu

PARENT_DIR = os.path.dirname(__file__)
PACKAGE_DIR = os.path.dirname(PARENT_DIR)
PLUGINS_DIR = os.path.join(PACKAGE_DIR, "plugins")

PUBLISH_PATH = os.path.join(PLUGINS_DIR, "maya", "publish")
LOAD_PATH = os.path.join(PLUGINS_DIR, "maya", "load")
CREATE_PATH = os.path.join(PLUGINS_DIR, "maya", "create")


def install():
    from mindbender import api as mindbender
    from pyblish import api as pyblish

    pyblish.register_plugin_path(PUBLISH_PATH)
    mindbender.register_plugin_path(mindbender.Loader, LOAD_PATH)
    mindbender.register_plugin_path(mindbender.Creator, CREATE_PATH)

    menu.install()


def uninstall():
    pyblish.deregister_plugin_path(PUBLISH_PATH)
    mindbender.deregister_plugin_path(mindbender.Loader, LOAD_PATH)
    mindbender.deregister_plugin_path(mindbender.Creator, CREATE_PATH)

    menu.uninstall()
