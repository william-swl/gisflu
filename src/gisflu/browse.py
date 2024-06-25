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
from typing import List

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.NullHandler())


def search(
    cred: credentials,
    type: List[str] | None = None,
    HA: List[str] | None = None,
    NA: List[str] | None = None,
    host: List[str] | None = None,
    collectDateFrom: str | None = None,
    collectDateTo: str | None = None,
    recordLimit: int = 50,
) -> pd.DataFrame:
    """
    Search for records in the GISAID Flu database based on specified criteria.

    Args:
        cred (credentials): The credentials object containing session information.
        type (List[str], optional): A list of virus types to filter the search results. Defaults to None.
        HA (List[str], optional): A list of hemagglutinin (HA) subtypes to filter the search results. Defaults to None.
        NA (List[str], optional): A list of neuraminidase (NA) subtypes to filter the search results. Defaults to None.
        host (List[str], optional): A list of host species to filter the search results. Defaults to None.
        collectDateFrom (str, optional): The starting date for the collection date filter. Defaults to None.
        collectDateTo (str, optional): The ending date for the collection date filter. Defaults to None.
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
