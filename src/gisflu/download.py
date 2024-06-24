import re
from .utils import (
    buildCommand,
    buildRequestBody,
    httpGet,
    httpPost,
    downloadToResultPage,
    resultToBrowsePage,
)
import logging
from datetime import datetime
import urllib

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.NullHandler())


def download(
    cred, isolateIds, downloadType="protein", segments=["HA", "NA"], filename=None
):
    assert all(
        id.startswith("EPI_ISL_") for id in isolateIds
    ), 'isolateId must start with "EPI_ISL_"'

    segmentCheck = [
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

    unknownSegments = [segment for segment in segments if segment not in segmentCheck]
    unknownSegmentStr = ", ".join(unknownSegments)
    assert len(unknownSegments) == 0, f"Unknown segment(s): {unknownSegmentStr}"

    logger.debug("Go to result page...")
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

    # select records, get download page id
    cmdPipe = [
        buildCommand(
            CompId=cred.resultPage["resultCompId"],
            cmd="ChangeValue",
            params={
                "row_id": acc.replace("EPI_ISL_", ""),
                "col_name": "c",
                "value": True,
            },
        )
        for acc in isolateIds
    ]
    cmdPipe += [buildCommand(CompId=cred.resultPage["downloadCompId"], cmd="Download")]

    body = buildRequestBody(
        cred.sessionId, cred.windowId, cred.resultPage["pid"], cmdPipe
    )

    res = httpPost(cred.url, data=body, headers=cred.headers)

    cred.downloadWindowId, cred.downloadPage["pid"] = re.search(
        r"sys.openOverlay\(\'(\w+?)\',\'(\w+?)\'", res.text
    ).group(1, 2)

    logger.debug("Go to download page...")
    # go to download overlay page
    res = httpGet(
        f'{cred.url}?sid={cred.sessionId}&pid={cred.downloadPage["pid"]}',
        headers=cred.headers,
    )
    resultDownloadCompId = cred.downloadPage["resultDownloadCompId"]
    downloadProteinSegmentCeid = cred.downloadParamsCeid["proteinSegment"]

    logger.debug("Set download params...")
    if downloadType.lower() == "metadata":
        cmdPipe = [
            buildCommand(CompId=resultDownloadCompId, cmd="download"),
        ]

        body = buildRequestBody(
            cred.sessionId, cred.downloadWindowId, cred.downloadPage["pid"], cmdPipe
        )

        res = httpPost(cred.url, data=body, headers=cred.headers)

        api = re.search(r"sys\.downloadFile\(\\\"(.+?)\\\"", res.text).group(1)
    elif downloadType.lower() == "protein":
        # select protein
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

        # check segment
        cmdPipe = [
            buildCommand(
                CompId=resultDownloadCompId,
                cmd="setTarget",
                params={"cvalue": ["HA", "NA"], "ceid": downloadProteinSegmentCeid},
                equiv=f"ST{downloadProteinSegmentCeid}",
            ),
            buildCommand(
                CompId=resultDownloadCompId,
                cmd="ChangeValue",
                params={"cvalue": ["HA", "NA"], "ceid": downloadProteinSegmentCeid},
                equiv=f"CV{downloadProteinSegmentCeid}",
            ),
            buildCommand(
                CompId=resultDownloadCompId,
                cmd="SelChange",
                params={"ceid": downloadProteinSegmentCeid},
            ),
            buildCommand(CompId=resultDownloadCompId, cmd="download"),
        ]

        body = buildRequestBody(
            cred.sessionId, cred.downloadWindowId, cred.downloadPage["pid"], cmdPipe
        )

        res = httpPost(cred.url, data=body, headers=cred.headers)

        api = re.search(r"sys\.downloadFile\(\\\"(.+?)\\\"", res.text).group(1)

    # download
    logger.debug("Downloading...")
    now = datetime.now().strftime("%Y%m%d-%H%M%S")
    count = len(isolateIds)
    if filename is None:
        if downloadType == "metadata":
            extension = "xls"
        elif downloadType in ["protein"]:
            extension = "fasta"
        filename = f"gisflu-{count}-{downloadType}-{now}.{extension}"

    downloadLink = "https://" + urllib.parse.urlparse(cred.url).hostname + api
    res = httpGet(downloadLink, headers=cred.headers)

    with open(filename, "wb") as f:
        f.write(res.content)

    downloadToResultPage(cred)
    resultToBrowsePage(cred)

    return None
