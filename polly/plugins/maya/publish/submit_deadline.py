import pyblish.api


class MindbenderSubmitDeadline(pyblish.api.InstancePlugin):
    """Submit available render layers to Deadline"""

    label = "Submit to Deadline"
    order = pyblish.api.IntegratorOrder
    hosts = ["maya"]
    families = ["mindbender.renderlayer"]

    def process(self, instance):
        import os
        import json
        import getpass

        from maya import cmds

        from avalon import api
        from avalon.vendor import requests

        context = instance.context
        workspace = context.data["workspaceDir"]
        fname = context.data["currentFile"]
        comment = context.data.get("comment", "")

        # Deadline prefers a single line for a comment
        comment, _, _ = comment.partition("\n")

        try:
            # E.g. http://192.168.0.1:8082/api/jobs
            url = api.Session["AVALON_DEADLINE"] + "/api/jobs"
        except KeyError:
            raise Exception("Missing session variable AVALON_DEADLINE")

        for key in ("startFrame", "endFrame", "byFrameStep"):
            value = instance.data[key]
            if int(value) != value:
                self.log.warning("%f=%d was rounded off to nearest integer"
                                 % (value, int(value)))

        payload = {
            "JobInfo": {
                "Name": "%s - %s" % (fname, instance.name),
                "BatchName": "%s - \"%s\"" % (fname, comment),
                "UserName": getpass.getuser(),
                "Plugin": "MayaBatch",
                "Frames": "{start}-{end}x{step}".format(
                    start=int(instance.data["startFrame"]),
                    end=int(instance.data["endFrame"]),
                    step=int(instance.data["byFrameStep"]),
                ),
                "Comment": comment,
            },
            "PluginInfo": {
                "OutputFilePath": os.path.join(workspace, "images"),
                "SceneFile": fname,
                "Version": cmds.about(version=True),
                "UsingRenderLayers": 1,
                "UseLegacyRenderLayers": 1,
                "RenderLayer": instance.name,
                "ProjectPath": workspace,
            },
            "AuxFiles": []
        }

        payload = json.dumps(payload, indent=4)
        self.log.info("Submitting..")
        self.log.info(payload)
        response = requests.post(url, data=payload)

        assert response.ok, response.text
