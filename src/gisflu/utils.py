import logging
import httpx
import json
import time
import stamina

client = httpx.Client(timeout=10)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.NullHandler())


def buildCommand(CompId, cmd, params={}, equiv=None):
    res = {"cid": CompId, "cmd": cmd, "params": params, "equiv": equiv}

    return res


def buildRequestBody(sessionId, windowId, pageId, cmdPipe, mode="ajax"):
    cmdPipeFill = {"queue": [{"wid": windowId, "pid": pageId, **d} for d in cmdPipe]}
    cmdJson = json.dumps(cmdPipeFill)
    now = time.time()
    timestamp = str(int(now * 1000))

    res = {
        "sid": sessionId,
        "wid": windowId,
        "pid": pageId,
        "data": cmdJson,
        "ts": timestamp,
        "mode": mode,
    }

    return res


def buildBrowseCommand(credentials, ident, value):
    # type check
    if ident in ["type", "HA", "NA", "host"]:
        assert isinstance(value, list), f"{ident} must be a list"
        value = [str(v) for v in value]
    elif ident in ["collectDateFrom", "collectDateTo"]:
        assert isinstance(value, str), f"{ident} must be a string"

    # host code
    if ident == "host":
        value = [credentials.hostCode[v.title()] for v in value]

    identCeid = credentials.browseParamsCeid[ident]

    res = [
        buildCommand(
            CompId=credentials.browsePage["browseFormCompId"],
            cmd="setTarget",
            params={"cvalue": value, "ceid": identCeid},
            equiv=f"ST{identCeid}",
        ),
        buildCommand(
            CompId=credentials.browsePage["browseFormCompId"],
            cmd="ChangeValue",
            params={"cvalue": value, "ceid": identCeid},
            equiv=f"CV{identCeid}",
        ),
        buildCommand(
            CompId=credentials.browsePage["browseFormCompId"],
            cmd=credentials.browseParamsCmd[ident],
            params={"ceid": identCeid},
        ),
    ]

    return res


def buildBatch(startIdx, endIdx, batchSize):
    res = []
    for i in range((endIdx - startIdx) // batchSize + 1):
        start = i * batchSize
        if i != (endIdx - startIdx) // batchSize:
            end = i * batchSize + batchSize - 1
        else:
            end = endIdx
        count = end - start + 1
        res.append({"start": start, "end": end, "count": count})

    return res


################## requests ####################


@stamina.retry(on=httpx.HTTPError, attempts=3)
def httpGet(url):
    res = client.get(url, follow_redirects=True)
    return res


@stamina.retry(on=httpx.HTTPError, attempts=3)
def httpPost(url, data, headers):
    res = client.post(url, data=data, headers=headers, follow_redirects=True)
    return res


################## page ####################


def backToBrowsePage(credentials):
    cmdPipe = [
        buildCommand(CompId=credentials.resultPage["downloadCompId"], cmd="GoBack")
    ]
    body = buildRequestBody(
        credentials.sessionId,
        credentials.windowId,
        credentials.resultPage["pid"],
        cmdPipe,
    )

    client.post(
        credentials.url, data=body, headers=credentials.headers, follow_redirects=True
    )

    browsePagePid = credentials.browsePage["pid"]
    client.get(f"{credentials.url}?sid={credentials.sessionId}&pid={browsePagePid}")

    return None


################## logger ####################
def log(level=logging.DEBUG):
    logger = logging.getLogger(__package__)
    handler = logging.StreamHandler()
    handler.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return None
