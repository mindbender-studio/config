import pyblish.api


class ValidateMindbenderProtectedScene(pyblish.api.ContextPlugin):
    """Guard against publishing a scene that has already been published"""

    label = "Protected Scene"
    order = pyblish.api.ValidatorOrder
    hosts = ["maya"]
    optional = True

    def process(self, context):
        import os
        from maya import cmds

        try:
            basename = os.path.basename(context.data["currentFile"])
            is_protected = cmds.getAttr("protect.basename") == basename
        except ValueError:
            is_protected = False

        assert not (
            cmds.file(renameToSave=True, query=True) or is_protected
        ), ("This file is protected, please save scene under a new name. "
            "If you are sure of what you are doing, you can override this "
            "warning by calling cmds.remove('protect')")
