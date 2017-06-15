import os

PACKAGE_DIR = os.path.dirname(__file__)
PLUGINS_DIR = os.path.join(PACKAGE_DIR, "plugins")


def install():
    from pyblish import api as pyblish
    publish_path = os.path.join(PLUGINS_DIR, "publish")

    print("Registering global plug-ins..")
    pyblish.register_plugin_path(publish_path)
