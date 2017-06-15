import os

PARENT_DIR = os.path.dirname(__file__)
PACKAGE_DIR = os.path.dirname(PARENT_DIR)
PLUGINS_DIR = os.path.join(PACKAGE_DIR, "plugins")


def install():
    from mindbender import api
    from pyblish import api as pyblish
    publish_path = os.path.join(PLUGINS_DIR, "maya", "publish")
    load_path = os.path.join(PLUGINS_DIR, "maya", "load")
    create_path = os.path.join(PLUGINS_DIR, "maya", "create")

    print("Registering Maya plug-ins..")
    pyblish.register_plugin_path(publish_path)
    api.register_plugin_path(api.Loader, load_path)
    api.register_plugin_path(api.Creator, create_path)
