import pyblish.api


class ValidateMindbenderImagePrefix(pyblish.api.InstancePlugin):
    """Image prefix is automatically handled by the pipeline"""

    label = "Image Prefix"
    order = pyblish.api.ValidatorOrder
    hosts = ["maya"]
    families = ["mindbender.renderlayer"]

    def process(self, instance):
        from maya import cmds

        image_prefix = cmds.getAttr("defaultRenderGlobals.imageFilePrefix")
        if image_prefix:
            self.log.warning("There was an image prefix: '%s'\n"
                             "Image prefixes are automatically managed by "
                             "the pipeline, one is not required and will not "
                             "be taken into account." % image_prefix)
