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
            **{i: "OnlyCount" for i in ["host", "collectDateFrom", "collectDateTo"]},
        }
        self.hostCode = {"Human": "101", "Animal": "102", "Avian": "103"}
        self.resultHeaderDict = {}
        self.downloadParamsCeid = {}

    def __repr__(self):
        return f"credentials(sid={self.sessionId})"
