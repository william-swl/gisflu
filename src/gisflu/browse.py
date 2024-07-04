import re
from .utils import (
    buildCommand,
    buildRequestBody,
    buildBrowseCommand,
    buildBatch,
    resultToBrowsePage,
    httpGet,
    httpPost,
)
from .credentials import credentials
from tqdm import tqdm
import pandas as pd
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.NullHandler())


def search(
    cred: credentials,
    searchPattern: str | None = None,
    type: list[str] | None = None,
    HA: list[str] | None = None,
    NA: list[str] | None = None,
    host: list[str] | None = None,
    collectDateFrom: str | None = None,
    collectDateTo: str | None = None,
    submitDateFrom: str | None = None,
    submitDateTo: str | None = None,
    requestSegments: list[str] | None = None,
    onlyComplete: bool = False,
    recordLimit: int = 50,
) -> pd.DataFrame:
    """
    Search for records in the GISAID Flu database based on specified criteria.

    Args:
        cred (credentials): The credentials object containing session information.
        searchPattern (str, optional): The search pattern, can be isolate id, isolate name, segement id and so on. Defaults to None.
        type (list[str], optional): A list of virus types to filter the search results. Defaults to None.
        HA (list[str], optional): A list of hemagglutinin (HA) subtypes to filter the search results. Defaults to None.
        NA (list[str], optional): A list of neuraminidase (NA) subtypes to filter the search results. Defaults to None.
        host (list[str], optional): A list of host species to filter the search results. Defaults to None.
        collectDateFrom (str, optional): The starting date for the collection date filter. Defaults to None.
        collectDateTo (str, optional): The ending date for the collection date filter. Defaults to None.
        submitDateFrom (str, optional): The starting date for the submission date filter. Defaults to None.
        submitDateTo (str, optional): The ending date for the submission date filter. Defaults to None.
        requestSegments (list[str], optional): A list of requested segments to filter the search results. Defaults to None.
        onlyComplete (bool, optional): Whether to only return records with complete sequences of requested segments. Defaults to False.
        recordLimit (int, optional): The maximum number of records to return. Defaults to 50.

    Return:
        pd.DataFrame: A DataFrame containing the search results.

    Example:
        ```
        cred = gisflu.login()
        gisflu.search(cred, type=["A"], HA=["3"], NA=["2"],
            collectDateFrom="2020-01-01", recordLimit=10)
        ```
    """

    # search by command pipeline
    cmdPipe = []
    if searchPattern:
        cmdPipe += buildBrowseCommand(cred, "searchPattern", searchPattern)
    if type:
        cmdPipe += buildBrowseCommand(cred, "type", type)
    if HA:
        cmdPipe += buildBrowseCommand(cred, "HA", HA)
    if NA:
        cmdPipe += buildBrowseCommand(cred, "NA", NA)
    if host:
        cmdPipe += buildBrowseCommand(cred, "host", host)
    if collectDateFrom:
        cmdPipe += buildBrowseCommand(cred, "collectDateFrom", collectDateFrom)
    if collectDateTo:
        cmdPipe += buildBrowseCommand(cred, "collectDateTo", collectDateTo)
    if submitDateFrom:
        cmdPipe += buildBrowseCommand(cred, "submitDateFrom", submitDateFrom)
    if submitDateTo:
        cmdPipe += buildBrowseCommand(cred, "submitDateTo", submitDateTo)
    if requestSegments:
        cmdPipe += buildBrowseCommand(cred, "requestSegments", requestSegments)
        if onlyComplete is True:
            cmdPipe += buildBrowseCommand(cred, "onlyComplete", ["y"])

    body = buildRequestBody(
        cred.sessionId, cred.windowId, cred.browsePage["pid"], cmdPipe
    )

    res = httpPost(cred.url, data=body, headers=cred.headers)

    # records count in the browse page
    preResultText = res.text

    recordCount, recordSeqCount = [
        int(i.replace(",", ""))
        for i in re.search(
            r"Total: ([\d,]+) viruses \(([\d,]+) sequences\)", preResultText
        ).group(1, 2)
    ]

    logger.info(f"{recordCount} records, {recordSeqCount} seqs found")

    # refresh result page id
    cmdPipe = [buildCommand(CompId=cred.browsePage["searchButtonCompId"], cmd="search")]
    body = buildRequestBody(
        cred.sessionId, cred.windowId, cred.browsePage["pid"], cmdPipe
    )
    res = httpPost(cred.url, data=body, headers=cred.headers)
    resultPagePid = re.search(r"sys.goPage\(\'(.+?)\'\)", res.text).group(1)
    cred.resultPage["pid"] = resultPagePid

    logger.debug("Parse result page...")
    # go to result page
    res = httpGet(
        f"{cred.url}?sid={cred.sessionId}&pid={resultPagePid}", headers=cred.headers
    )
    resultPageText = res.text
    cred.resultPage["resultCompId"] = re.search(
        r"sys\.createComponent\(\'(c_\w+?)\',\'IsolateResultListComponent\'",
        resultPageText,
    ).group(1)

    logger.debug("Fetch result records...")
    # fetch records
    if recordCount > 0:
        resultJson = []

        batches = buildBatch(0, min(recordCount, recordLimit) - 1, batchSize=27)
        for batch in tqdm(batches):
            cmdPipe = [
                buildCommand(
                    CompId=cred.resultPage["resultCompId"],
                    cmd="SetPaginating",
                    params={
                        "start_index": batch["start"],
                        "rows_per_page": batch["count"],
                    },
                ),
                buildCommand(CompId=cred.resultPage["resultCompId"], cmd="GetData"),
            ]

            body = buildRequestBody(
                cred.sessionId, cred.windowId, cred.resultPage["pid"], cmdPipe
            )
            res = httpPost(cred.url, data=body, headers=cred.headers)

            resultJson += res.json()["records"]

        # records dataframe
        reslutDF = pd.DataFrame(resultJson)

        reslutDF = reslutDF.drop(
            [s for s in reslutDF.columns if s not in cred.resultHeaderDict.keys()],
            axis=1,
        )

        reslutDF = reslutDF.rename(columns=cred.resultHeaderDict)

        reslutDF = reslutDF.drop(["__toggle__", "edit", "HE", "P3"], axis=1)

        for col in ["Name", "PB2", "PB1", "PA", "HA", "NP", "NA", "MP", "NS"]:
            reslutDF[col] = reslutDF[col].str.replace(
                r"^.+?>(.+?)</.+$", r"\1", regex=True
            )
    else:
        reslutDF = pd.DataFrame()

    resultToBrowsePage(cred)

    nrow = reslutDF.shape[0]
    logger.debug(f"Search completed: return {nrow} rows")

    return reslutDF
