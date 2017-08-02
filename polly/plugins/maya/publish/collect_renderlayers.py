import pyblish.api


class CollectMindbenderMayaRenderlayers(pyblish.api.ContextPlugin):
    """Gather instances by active render layers"""

    order = pyblish.api.CollectorOrder
    hosts = ["maya"]
    label = "Render Layers"

    def process(self, context):
        from maya import cmds
        from avalon import maya, api

        def render_global(attr):
            return cmds.getAttr("defaultRenderGlobals." + attr)

        for layer in cmds.ls(type="renderLayer"):
            if layer.endswith("defaultRenderLayer"):
                continue

            data = {
                "family": "Render Layers",
                "families": ["mindbender.renderlayer"],
                "publish": cmds.getAttr(layer + ".renderable"),
                "startFrame": render_global("startFrame"),
                "endFrame": render_global("endFrame"),
                "byFrameStep": render_global("byFrameStep"),
                "renderer": render_global("currentRenderer"),

                "time": context.data["time"],
                "author": context.data["user"],
                "source": context.data["currentFile"].replace(
                    api.registered_root(), "{root}"
                ).replace("\\", "/"),
            }

            # Apply each user defined attribute as data
            for attr in cmds.listAttr(layer, userDefined=True) or list():
                try:
                    value = cmds.getAttr(layer + "." + attr)
                except Exception:
                    # Some attributes cannot be read directly,
                    # such as mesh and color attributes. These
                    # are considered non-essential to this
                    # particular publishing pipeline.
                    value = None

                data[attr] = value

            # Include (optional) global settings
            # TODO(marcus): Take into account layer overrides
            try:
                avalon_globals = maya.lsattr("id", "avalon.renderglobals")[0]
            except IndexError:
                pass
            else:
                avalon_globals = maya.read(avalon_globals)
                data["renderGlobals"] = {
                    key: value for key, value in {
                        "Pool": avalon_globals["pool"],
                        "Group": avalon_globals["group"],
                        "Frames": avalon_globals["frames"],
                        "Priority": avalon_globals["priority"],
                    }.items()

                    # Here's the kicker. These globals override defaults
                    # in the submission integrator, but an empty value
                    # means no overriding is made. Otherwise, Frames
                    # would override the default frames set under globals.
                    if value
                }

            instance = context.create_instance(layer)
            instance.data.update(data)
