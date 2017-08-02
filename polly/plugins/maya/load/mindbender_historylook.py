import avalon.maya


class HistoryLookLoader(avalon.maya.Loader):
    """Specific loader for lookdev"""

    families = ["mindbender.historyLookdev"]
    representations = ["ma"]

    def process(self, name, namespace, context, data):
        from maya import cmds

        nodes = cmds.file(
            self.fname,
            namespace=namespace,
            reference=True,
            returnNewNodes=True,
            groupReference=True,
            groupName=namespace + ":" + name
        )

        self[:] = nodes
