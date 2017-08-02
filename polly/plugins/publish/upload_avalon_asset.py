from pyblish import api
from avalon.api import Session


class UploadAvalonAsset(api.InstancePlugin):
    """Write to files and metadata

    This plug-in exposes your data to others by encapsulating it
    into a new version.

    """

    label = "Upload"
    order = api.IntegratorOrder + 0.1
    depends = ["IntegrateAvalonAsset"]
    optional = True

    active = bool(Session.get("AVALON_UPLOAD"))

    families = [
        "mindbender.model",
        "mindbender.rig",
        "mindbender.animation",
        "mindbender.lookdev",
        "mindbender.historyLookdev",
        "mindbender.group",
        "mindbender.imagesequence",
    ]

    def process(self, instance):
        from avalon import api
        from avalon.vendor import requests

        # Dependencies
        AVALON_LOCATION = api.Session["AVALON_LOCATION"]
        AVALON_USERNAME = api.Session["AVALON_USERNAME"]
        AVALON_PASSWORD = api.Session["AVALON_PASSWORD"]

        for src in instance.data["output"]:
            assert src.startswith(api.registered_root()), (
                "Output didn't reside on root, this is a bug"
            )

            dst = src.replace(
                api.registered_root(),
                AVALON_LOCATION + "/upload"
            ).replace("\\", "/")

            self.log.info("Uploading %s -> %s" % (src, dst))

            auth = requests.auth.HTTPBasicAuth(
                AVALON_USERNAME, AVALON_PASSWORD
            )

            with open(src) as f:
                response = requests.put(
                    dst,
                    data=f,
                    auth=auth,
                    headers={"Content-Type": "application/octet-stream"}
                )

                if not response.ok:
                    raise Exception(response.text)
