class credentials:
    def __init__(self):
        self.url = "https://platform.epicov.org/epi3/frontend"
        self.headers = {
            "accept": "application/json, text/javascript, */*; q=0.01",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        self.sessionId = None
        self.windowId = None
        self.downloadWindowId = None
        self.loginPage = {"pid": None, "loginCompId": None}
        self.firstPage = {"pid": None, "dbSwitchCompId": None}
        self.homePage = {"pid": None, "browseCompId": None}
        self.browsePage = {
            "pid": None,
            "browseFormCompId": None,
            "searchButtonCompId": None,
        }
        self.resultPage = {
            "pid": None,
            "resultCompId": None,
            "downloadCompId": None,
        }
        self.downloadPage = {"pid": None, "resultDownloadCompId": None}
        self.browseParamsCeid = {}
        self.browseParamsCmd = {
            **{i: "TypeChanged" for i in ["type", "HA", "NA"]},
            **{
                i: "OnlyCount"
                for i in [
                    "searchPattern",
                    "host",
                    "location",
                    "collectDateFrom",
                    "collectDateTo",
                    "submitDateFrom",
                    "submitDateTo",
                    "onlyComplete",
                ]
            },
            **{i: "LineageChanged" for i in ["lineage"]},
            **{i: "ReqSegChanged" for i in ["requestSegments"]},
        }
        self.hostCode = {
            "Human": "101",
            "Animal": "102",
            "Avian": "103",
            "Mammals": "790",
        }
        self.resultHeaderDict = {}
        self.downloadParamsCeid = {}
        self.segmentCheck = [
            "NP",
            "P3",
            "HA",
            "M1",
            "M2",
            "BM2",
            "CM2",
            "M",
            "NA",
            "NB",
            "NS1",
            "NEP",
            "NS2",
            "PA",
            "PA-X",
            "PB1-F2",
            "PB1",
            "HE",
            "PB2",
        ]

        self.downloadWaitWindowId = None
        self.downloadWaitPage = {
            "pid": None,
            "waitCompId": None,
        }
        self.downloadWaitCeid = {}

    def __repr__(self):
        return f"credentials(sid={self.sessionId})"
