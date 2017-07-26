import pyblish.api


class ValidateMindbenderLockedScene(pyblish.api.ContextPlugin):
    """Guard against publishing a scene that has already been published"""

    label = "Locked Scene"
    order = pyblish.api.ValidatorOrder
    hosts = ["maya"]
    optional = True

    def process(self, context):
        import os
        from maya import cmds

        try:
            basename = os.path.basename(context.data["currentFile"])
            is_locked = cmds.getAttr("lock.basename") == basename
        except ValueError:
            is_locked = False

        assert not (
            cmds.file(renameToSave=True, query=True) or is_locked
        ), ("This file is locked, please save scene under a new name. "
            "If you are sure of what you are doing, you can override this "
            "warning by calling cmds.remove('lock')")
