import pyblish.api


class AvalonProtectScene(pyblish.api.ContextPlugin):
    """Prevent accidental overwrite of original scene once published

    A node is placed within the scene where the name of the file
    as it exists currently is imprinted. If an attempt is made to
    publish this file where the name of the file and that in the lock
    is a match, publishing fails.

    """

    label = "Protect Scene"
    order = pyblish.api.IntegratorOrder + 0.5
    optional = True

    def process(self, context):
        import os
        from maya import cmds

        assert all(result["success"] for result in context.data["results"]), (
            "Integration failed, aborting.")

        # Install persistent lock
        if not cmds.objExists("protect"):
            cmds.createNode("objectSet", name="protect")
            cmds.addAttr("protect", ln="basename", dataType="string")

            # Permanently hide from outliner
            cmds.setAttr("protect.verticesOnlySet", True)

        basename = os.path.basename(context.data["currentFile"])
        cmds.setAttr("protect.basename", basename, type="string")

        cmds.file(save=True, force=True)
        cmds.file(renameToSave=True)
