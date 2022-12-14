# MLPerf result summarizer

MLPerf result summarizer

## Usage

To summarize an organization's submission results:

```sh
python3 -m mlperf_logging.result_summarizer FOLDER USAGE RULESET
```

Alternatively, multiple organizations' submissions can be processed:

Currently, USAGE in ["training"] and RULESET in ["0.6.0", "0.7.0", "1.0.0", "1.1.0", "2.0.0"] are supported.
FOLDER can be a single organization's submission folder like
`/path/to/training_results_v0.6/COMPANY_NAME`. For example,
```sh
python3 -m mlperf_logging.result_summarizer ../training_results_v0.7/Google/ training 0.7.0
```
Alternatively, FOLDER can be a
multi-org pattern like `"/path/to/training_results_v0.6/{COMPANY_A,COMPANY_B}"`
or a wildcard pattern like `"../training_results_v0.6/{\*}"`. For example,
```sh
python3 -m mlperf_logging.result_summarizer "../training_results_v1.0/{Google,NVIDIA}" training 1.0.0
# or
python3 -m mlperf_logging.result_summarizer "../training_results_v1.0/{*}" training 1.0.0
```

With the `--csv` flag, the result summarizer exports a CSV line for each system, 
corresponding to one row of a table like the 
[0.6 results](https://mlperf.org/training-results-0-6).

## Tested software versions
Tested and confirmed working using the following software versions:

Python 3.7.7 
Python 3.9.2
Python 3.9.10
