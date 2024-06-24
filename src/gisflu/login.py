import os
import hashlib
import re
from .credentials import credentials
from .utils import (
    buildCommand,
    buildRequestBody,
    resultToBrowsePage,
    downloadToResultPage,
    httpGet,
    httpPost,
)
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.NullHandler())


def login(username=None, password=None):
    cred = credentials()

    # get username and password
    if username is None or password is None:
        logger.debug(
            "Username and password not provided, fetching from environment variables"
        )

        username = os.getenv("GISAID_USERNAME")
        password = os.getenv("GISAID_PASSWORD")

        assert (
            username is not None
        ), 'Please set the environment variable "GISAID_USERNAME"'
        assert (
            password is not None
        ), 'Please set the environment variable "GISAID_PASSWORD"'

    password_md5 = hashlib.md5(password.encode()).hexdigest()

    # fetch sessionId first
    res = httpGet(cred.url, headers=cred.headers)
    cred.sessionId = re.search(r'name="sid" value=\'(.+?)\'', res.text).group(1)
    logger.debug(f"Get sessionId: {cred.sessionId}")

    # then get login page, to get more ids
    res = httpGet(f"{cred.url}?sid={cred.sessionId}", headers=cred.headers)
    loginPageText = res.text
    cred.windowId = re.search(r'sys\["WID"\] = "(.+?)";', loginPageText).group(1)
    cred.loginPage["pid"] = re.search(r'sys\["PID"\] = "(.+?)";', loginPageText).group(
        1
    )
    cred.loginPage["loginCompId"] = re.search(
        r"sys.getC\(\'(.+?)\'\).call\(\'doLogin\'", loginPageText
    ).group(1)

    # login by command pipeline
    cmdPipe = [
        buildCommand(
            CompId=cred.loginPage["loginCompId"],
            cmd="doLogin",
            params={"login": username, "hash": password_md5},
        )
    ]

    body = buildRequestBody(
        cred.sessionId, cred.windowId, cred.loginPage["pid"], cmdPipe, mode="ajax"
    )

    res = httpPost(cred.url, data=body, headers=cred.headers)
    assert re.search("cms_page", res.text), "Username or password wrong!"
    logger.debug("username and password validated!")

    # first page after login
    logger.debug("Go to first page...")
    res = httpGet(f"{cred.url}?sid={cred.sessionId}", headers=cred.headers)
    firstPageText = res.text
    cred.firstPage["pid"] = re.search(r'sys\["PID"\] = "(.+?)";', firstPageText).group(
        1
    )
    cred.firstPage["dbSwitchCompId"] = re.search(
        r"sys.call\(\'(.+?)\',\'Go\'", firstPageText
    ).group(1)

    # fetch flu home page id by command pipeline
    logger.debug("Go to flu homepage...")
    cmdPipe = [
        buildCommand(
            CompId=cred.firstPage["dbSwitchCompId"], cmd="Go", params={"page": "epi3"}
        )
    ]

    body = buildRequestBody(
        cred.sessionId, cred.windowId, cred.firstPage["pid"], cmdPipe
    )

    res = httpPost(cred.url, data=body, headers=cred.headers)
    homePagePid = re.search(r"sys.goPage\(\'(.+?)\'\)", res.text).group(1)
    cred.homePage["pid"] = homePagePid

    # go to flu home page
    res = httpGet(
        f"{cred.url}?sid={cred.sessionId}&pid={homePagePid}", headers=cred.headers
    )
    homePageText = res.text

    ################## browse page ####################
    logger.debug("Parse browse page...")

    # fetch browse(search) page id
    cred.homePage["browseCompId"] = re.search(
        r"class=\"sys-actionbar-action-ni\" onclick=\"sys.getC\(\'(.+?)\'\)",
        homePageText,
    ).group(1)

    cmdPipe = [buildCommand(CompId=cred.homePage["browseCompId"], cmd="Browse")]

    body = buildRequestBody(
        cred.sessionId, cred.windowId, cred.homePage["pid"], cmdPipe
    )

    res = httpPost(cred.url, data=body, headers=cred.headers)

    browsePagePid = re.search(r"sys.goPage\(\'(.+?)\'\)", res.text).group(1)
    cred.browsePage["pid"] = browsePagePid

    # go to browse page
    res = httpGet(
        f"{cred.url}?sid={cred.sessionId}&pid={browsePagePid}", headers=cred.headers
    )
    browsePageText = res.text

    cred.browsePage["browseFormCompId"] = re.search(
        r"sys\.createComponent\(\'(c_\w+?)\',\'IsolateBrowseFormComponent\'",
        browsePageText,
    ).group(1)

    cred.browsePage["searchButtonCompId"] = re.search(
        r"sys\.createComponent\(\'(c_\w+?)\',\'IsolateSearchButtonsComponent\'",
        browsePageText,
    ).group(1)

    # fetch browse component event id
    browseItemText = re.findall(r"createFI\(.+?function", browsePageText)

    browseItemDict = {}
    for s in browseItemText:
        ident = re.search(r"Widget\',\'(.+?)\',function", s).group(1)
        ceid = re.search(r"createFI\(\'(.+?)\',", s).group(1)
        browseItemDict[ident] = ceid

    cred.browseParamsCeid["type"] = browseItemDict["isl_type"]
    cred.browseParamsCeid["HA"] = browseItemDict["isl_subtype_h"]
    cred.browseParamsCeid["NA"] = browseItemDict["isl_subtype_n"]
    cred.browseParamsCeid["lineage"] = browseItemDict["isl_lineage"]
    cred.browseParamsCeid["host"] = browseItemDict["isl_host"]
    cred.browseParamsCeid["location"] = browseItemDict["isl_location"]
    cred.browseParamsCeid["collectDateFrom"] = browseItemDict["isl_collect_date_from"]
    cred.browseParamsCeid["collectDateTo"] = browseItemDict["isl_collect_date_to"]

    ################## result page ####################
    logger.debug("Parse result page...")

    # fetch result page id
    cmdPipe = [buildCommand(CompId=cred.browsePage["searchButtonCompId"], cmd="search")]
    body = buildRequestBody(
        cred.sessionId, cred.windowId, cred.browsePage["pid"], cmdPipe
    )
    res = httpPost(cred.url, data=body, headers=cred.headers)
    resultPagePid = re.search(r"sys.goPage\(\'(.+?)\'\)", res.text).group(1)
    cred.resultPage["pid"] = resultPagePid

    # go to result page
    res = httpGet(
        f"{cred.url}?sid={cred.sessionId}&pid={resultPagePid}", headers=cred.headers
    )
    resultPageText = res.text
    cred.resultPage["resultCompId"] = re.search(
        r"sys\.createComponent\(\'(c_\w+?)\',\'IsolateResultListComponent\'",
        resultPageText,
    ).group(1)
    cred.resultPage["downloadCompId"] = re.search(
        r"sys\.createComponent\(\'(c_\w+?)\',\'IsolateDownloadButtonComponent\'",
        resultPageText,
    ).group(1)

    # parse result table header
    tableHeaderText = re.findall(r"new Object\(\{\'label.+?cid", resultPageText)

    for s in tableHeaderText:
        label = re.search(r"label\':\'([\w ]+?)\'", s).group(1)
        key = re.search(r"key\':\'(\w+?)\'", s).group(1)
        cred.resultHeaderDict[key] = label

    ################## download page ####################
    logger.debug("Parse download page...")

    # get a temp record
    cmdPipe = [
        buildCommand(
            CompId=cred.resultPage["resultCompId"],
            cmd="SetPaginating",
            params={"start_index": 0, "rows_per_page": 27},
        ),
        buildCommand(CompId=cred.resultPage["resultCompId"], cmd="GetData"),
    ]

    body = buildRequestBody(
        cred.sessionId, cred.windowId, cred.resultPage["pid"], cmdPipe
    )
    res = httpPost(cred.url, data=body, headers=cred.headers)

    tempRecordId = res.json()["records"][0]["b"]

    # select this temp record
    cmdPipe = [
        buildCommand(
            CompId=cred.resultPage["resultCompId"],
            cmd="ChangeValue",
            params={"row_id": tempRecordId, "col_name": "c", "value": True},
        ),
        buildCommand(CompId=cred.resultPage["downloadCompId"], cmd="Download"),
    ]

    body = buildRequestBody(
        cred.sessionId, cred.windowId, cred.resultPage["pid"], cmdPipe
    )

    res = httpPost(cred.url, data=body, headers=cred.headers)

    cred.downloadWindowId, cred.downloadPage["pid"] = re.search(
        r"sys.openOverlay\(\'(\w+?)\',\'(\w+?)\'", res.text
    ).group(1, 2)

    # go to download overlay page
    res = httpGet(
        f'{cred.url}?sid={cred.sessionId}&pid={cred.downloadPage["pid"]}',
        headers=cred.headers,
    )
    downloadPageText = res.text

    cred.downloadPage["resultDownloadCompId"] = re.search(
        r"sys\.createComponent\(\'(c_\w+?)\',\'IsolateResultDownloadComponent\'",
        downloadPageText,
    ).group(1)

    # fetch download item ceid
    downloadItemText = re.findall(r"createFI\(.+?function", downloadPageText)

    downloadItemDict = {}
    for s in downloadItemText:
        ident = re.search(r"Widget\',\'(.+?)\',function", s).group(1)
        ceid = re.search(r"createFI\(\'(.+?)\',", s).group(1)
        downloadItemDict[ident] = ceid

    cred.downloadParamsCeid["downloadFormat"] = downloadItemDict["format"]
    cred.downloadParamsCeid["downloadConfirm"] = downloadItemDict["download"]

    # fetch protein segment ceid

    cmdPipe = [
        buildCommand(
            CompId=cred.downloadPage["resultDownloadCompId"],
            cmd="setTarget",
            params={
                "cvalue": "proteins",
                "ceid": cred.downloadParamsCeid["downloadFormat"],
            },
            equiv=f'ST{cred.downloadParamsCeid["downloadFormat"]}',
        ),
        buildCommand(
            CompId=cred.downloadPage["resultDownloadCompId"],
            cmd="ChangeValue",
            params={
                "cvalue": "proteins",
                "ceid": cred.downloadParamsCeid["downloadFormat"],
            },
            equiv=f'CV{cred.downloadParamsCeid["downloadFormat"]}',
        ),
        buildCommand(
            CompId=cred.downloadPage["resultDownloadCompId"],
            cmd="ShowProteins",
            params={"ceid": cred.downloadParamsCeid["downloadFormat"]},
        ),
    ]

    body = buildRequestBody(
        cred.sessionId, cred.downloadWindowId, cred.downloadPage["pid"], cmdPipe
    )

    res = httpPost(cred.url, data=body, headers=cred.headers)

    downloadProteinText = res.text

    cred.downloadParamsCeid["proteinSegment"] = re.search(
        r"createFI\(\'(\w+?)\',\'CheckboxWidget\',\'proteins\'", downloadProteinText
    ).group(1)

    # fetch dna segment ceid
    cmdPipe = [
        buildCommand(
            CompId=cred.downloadPage["resultDownloadCompId"],
            cmd="setTarget",
            params={
                "cvalue": "dna",
                "ceid": cred.downloadParamsCeid["downloadFormat"],
            },
            equiv=f'ST{cred.downloadParamsCeid["downloadFormat"]}',
        ),
        buildCommand(
            CompId=cred.downloadPage["resultDownloadCompId"],
            cmd="ChangeValue",
            params={
                "cvalue": "dna",
                "ceid": cred.downloadParamsCeid["downloadFormat"],
            },
            equiv=f'CV{cred.downloadParamsCeid["downloadFormat"]}',
        ),
        buildCommand(
            CompId=cred.downloadPage["resultDownloadCompId"],
            cmd="ShowProteins",
            params={"ceid": cred.downloadParamsCeid["downloadFormat"]},
        ),
    ]

    body = buildRequestBody(
        cred.sessionId, cred.downloadWindowId, cred.downloadPage["pid"], cmdPipe
    )

    res = httpPost(cred.url, data=body, headers=cred.headers)

    downloadDNAText = res.text

    cred.downloadParamsCeid["dnaSegment"] = re.search(
        r"createFI\(\'(\w+?)\',\'CheckboxWidget\',\'dna\'", downloadDNAText
    ).group(1)

    cred.downloadParamsCeid["fastaHeader"] = re.search(
        r"createFI\(\'(\w+?)\',\'EntryWidget\',\'header\'", downloadDNAText
    ).group(1)

    ################## return browse page ####################
    downloadToResultPage(cred)
    resultToBrowsePage(cred)
    logger.debug(f"{username} logged!")

    return cred
