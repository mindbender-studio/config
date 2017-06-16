import os
from pyblish import api as pyblish

PACKAGE_DIR = os.path.dirname(__file__)
PLUGINS_DIR = os.path.join(PACKAGE_DIR, "plugins")
PUBLISH_PATH = os.path.join(PLUGINS_DIR, "publish")


def install():
    print("Registering global plug-ins..")
    pyblish.register_plugin_path(PUBLISH_PATH)


def uninstall():
    pyblish.deregister_plugin_path(PUBLISH_PATH)
