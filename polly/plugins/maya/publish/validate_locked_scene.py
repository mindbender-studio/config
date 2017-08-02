import pyblish.api


class ValidateMindbenderLockedScene(pyblish.api.ContextPlugin):
    """Guard against publishing a scene that has already been published"""

    label = "Locked Scene"
    order = pyblish.api.ValidatorOrder
    hosts = ["maya"]
    optional = True

    def process(self, context):
        from avalon import maya

        assert not maya.is_locked(), (
            "This file is locked, please save scene under a new name. "
            "If you are sure of what you are doing, you can override this "
            "warning by calling cmds.remove('lock')"
        )
