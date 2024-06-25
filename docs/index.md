# gisflu

Access the GISAID Flu database using Python. Inspired by [GISAIDR](https://github.com/Wytamma/GISAIDR/tree/master), which is an R package for accessing the EpiCoV, EpiRSV and EpiPox database of GISAID.

## install

```sh
# use pip
pip install gisflu
# use pdm
pdm add gisflu
```

## login

```python
import gisflu

# Log in with provided username and password
gisflu.login("myusername", "mypassword")

# Log in using environment variables
gisflu.login()
```

## search

```python
cred = gisflu.login()
gisflu.search(cred, type=["A"], HA=["3"], NA=["2"],
    collectDateFrom="2020-01-01", recordLimit=10)
```

## download

```python
cred = gisflu.login()
isolateIds = ["EPI_ISL_19185107", "EPI_ISL_19151100"]
gisflu.download(cred, isolateIds, downloadType="protein", segments=["HA", "NA"],
    filename="records.fasta")
```
