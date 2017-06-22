import pyblish.api


class CollectAvalonComment(pyblish.api.ContextPlugin):
    """This plug-ins displays the comment dialog box per default"""

    label = "Collect Avalon Time"
    order = pyblish.api.CollectorOrder

    def process(self, context):
        context.data["comment"] = ""
