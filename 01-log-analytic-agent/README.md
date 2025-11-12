# OCI Generative AI Agent for Log Analytics

## Overview
This application uses the OCI Generative AI Agent to analyze log data. It provides a Streamlit-based interface for uploading CSV files and querying the data using natural language.

## Prerequisites
1. Install required packages: `pip install -r requirements.txt`
2. Configure OCI credentials (see [OCI documentation](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/sdkconfig.htm))
3. Update line no 7 and 8 with the respective oci generative ai agent endpoint ocid and region.
```python
AGENT_ENDPOINT_ID = "ocid1.genaiagentendpoint.oc1.eu-frankfurt-1.xxxxx"
REGION = "eu-frankfurt-1"
```

## Usage
1. Run the application: `streamlit run main.py`
2. Upload a CSV file containing log data
3. Ask questions about your log data using natural language

## Features
- CSV upload and processing
- Natural language querying of log data
- Contextual chat interface

## Notes
- Ensure your CSV file is properly formatted
- Be mindful of OCI API limits when processing large datasets

