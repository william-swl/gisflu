import re
from .utils import (
    buildCommand,
    buildRequestBody,
    httpGet,
    httpPost,
    downloadToResultPage,
    resultToBrowsePage,
)
from .credentials import credentials
import logging
from datetime import datetime
import urllib
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.NullHandler())


def download(
    cred: credentials,
    isolateIds: list[str],
    downloadType: str = "protein",
    segments: list[str] = ["HA", "NA"],
    filename: str | None = None,
) -> None:
    """
    Downloads records for the given isolate IDs.

    Args:
        cred (object): The credentials object.
        isolateIds (list): list of isolate IDs to download data for.
        downloadType (str, optional): The type of data to download. Defaults to "protein".
        segments (list, optional): list of segments to download. Defaults to ["HA", "NA"].
        filename (str, optional): The name of the file to save the downloaded data. If not provided, a default filename will be generated.

    Return:
        None

    Example:
        ```
        cred = gisflu.login()
        isolateIds = ["EPI_ISL_19185107", "EPI_ISL_19151100"]
        gisflu.download(cred, isolateIds, downloadType="protein", segments=["HA", "NA"],
            filename="records.fasta")
        ```
    """

    assert all(
        id.startswith("EPI_ISL_") for id in isolateIds
    ), 'isolateId must start with "EPI_ISL_"'

    assert downloadType in [
        "metadata",
        "protein",
        "dna",
    ], "downloadType must be metadata|protein|dna"

    unknownSegments = [
        segment for segment in segments if segment not in cred.segmentCheck
    ]
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

    logger.debug("Set download params...")
    if downloadType == "metadata":
        cmdPipe = [
            buildCommand(CompId=resultDownloadCompId, cmd="download"),
        ]

        body = buildRequestBody(
            cred.sessionId, cred.downloadWindowId, cred.downloadPage["pid"], cmdPipe
        )

        res = httpPost(cred.url, data=body, headers=cred.headers)

        # wait for a big metadata download
        if "sys.openOverlay" in res.text:
            logger.debug("Go to metadata download wait page...")
            cred.downloadWaitWindowId, downloadWaitPagePid = re.search(
                r"sys\.openOverlay\('(.+?)','(.+?)',new Object", res.text
            ).group(1, 2)

            # go to downloadWaitPage, get waitCompId
            cred.downloadWaitPage["pid"] = downloadWaitPagePid
            res = httpGet(
                f"{cred.url}?sid={cred.sessionId}&wid={cred.downloadWaitWindowId}&pid={downloadWaitPagePid}",
                headers=cred.headers,
            )

            waitCompId = re.search(
                r"sys\.createComponent\(\'(c_\w+?)\',\'XLSDownloadWaitFormComponent\'",
                res.text,
            ).group(1)

            cred.downloadWaitPage["waitCompId"] = waitCompId
            pingerWidgetCeid = re.search(
                r"createFI\(\'(\w+?)\',\'PingerWidget\',\'ping\'", res.text
            ).group(1)
            cred.downloadWaitCeid["pingerWidget"] = pingerWidgetCeid

            # wait
            while True:
                logger.debug("Wait for the metadata download link...")
                time.sleep(5)
                cmdPipe = [
                    buildCommand(
                        CompId=waitCompId,
                        cmd="PingerPing",
                        params={
                            "ceid": pingerWidgetCeid,
                        },
                    ),
                ]

                body = buildRequestBody(
                    cred.sessionId,
                    cred.downloadWaitWindowId,
                    cred.downloadWaitPage["pid"],
                    cmdPipe,
                )

                res = httpPost(cred.url, data=body, headers=cred.headers)

                if "sys.downloadFile" in res.text:
                    break

        logger.debug("Get the metadata download link!")
        api = re.search(r"sys\.downloadFile\(\\\"(.+?)\\\"", res.text).group(1)

    elif downloadType in ["protein", "dna"]:
        if downloadType == "protein":
            typeCvalue = "proteins"
            downloadSegmentCeid = cred.downloadParamsCeid["proteinSegment"]
            faHeader = "Protein Accession no.|Gene name|Isolate name|Isolate ID|Type@Collection date"
        else:
            typeCvalue = "dna"
            downloadSegmentCeid = cred.downloadParamsCeid["dnaSegment"]
            faHeader = (
                "DNA Accession no.|Segment|Isolate name|Isolate ID|Type@Collection date"
            )

        resultDownloadCompId = cred.downloadPage["resultDownloadCompId"]
        downloadFormatCeid = cred.downloadParamsCeid["downloadFormat"]
        fastaHeaderCeid = cred.downloadParamsCeid["fastaHeader"]

        cmdPipe = [
            # select protein|dna
            buildCommand(
                CompId=resultDownloadCompId,
                cmd="setTarget",
                params={
                    "cvalue": typeCvalue,
                    "ceid": downloadFormatCeid,
                },
                equiv=f"ST{downloadFormatCeid}",
            ),
            buildCommand(
                CompId=resultDownloadCompId,
                cmd="ChangeValue",
                params={
                    "cvalue": typeCvalue,
                    "ceid": downloadFormatCeid,
                },
                equiv=f"CV{downloadFormatCeid}",
            ),
            buildCommand(
                CompId=resultDownloadCompId,
                cmd="ShowProteins",
                params={"ceid": downloadFormatCeid},
            ),
            # check segment
            buildCommand(
                CompId=resultDownloadCompId,
                cmd="setTarget",
                params={"cvalue": segments, "ceid": downloadSegmentCeid},
                equiv=f"ST{downloadSegmentCeid}",
            ),
            buildCommand(
                CompId=resultDownloadCompId,
                cmd="ChangeValue",
                params={"cvalue": segments, "ceid": downloadSegmentCeid},
                equiv=f"CV{downloadSegmentCeid}",
            ),
            buildCommand(
                CompId=resultDownloadCompId,
                cmd="SelChange",
                params={"ceid": downloadSegmentCeid},
            ),
            # set fasta header
            buildCommand(
                CompId=resultDownloadCompId,
                cmd="setTarget",
                params={"cvalue": faHeader, "ceid": fastaHeaderCeid},
                equiv=f"ST{fastaHeaderCeid}",
            ),
            buildCommand(
                CompId=resultDownloadCompId,
                cmd="ChangeValue",
                params={"cvalue": faHeader, "ceid": fastaHeaderCeid},
                equiv=f"CV{fastaHeaderCeid}",
            ),
            buildCommand(
                CompId=resultDownloadCompId,
                cmd="fillExampleCopied",
                params={"ceid": fastaHeaderCeid},
            ),
            # download
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
        elif downloadType in ["protein", "dna"]:
            extension = "fasta"
        filename = f"gisflu-{downloadType}-{count}records-{now}.{extension}"

    downloadLink = "https://" + urllib.parse.urlparse(cred.url).hostname + api
    res = httpGet(downloadLink, headers=cred.headers)

    with open(filename, "wb") as f:
        f.write(res.content)

    downloadToResultPage(cred)
    resultToBrowsePage(cred)

    return None
