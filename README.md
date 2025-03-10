# iterative-llm-research-ollama
An automated research pipeline that uses local LLMs to generate an extensive initial answer for a research topic, iteratively refines that answer by integrating web-sourced data, and produces a final Markdown essay.

The idea to develop is the following:

1. A user come up with a research question. 
2. A local LLM develop an initial explanation of the topic 
3. The LLM then create the assay and come up with a question related to further explore a potential gap or future research point. 
4. The system then performs a web research, gather some extra information from, combine it and refine the the assay. 
5. The system now repeats 3. and 4. for N times and keep on generating new paragraphs in the final assay. 
6. Finally, the LLM act as an expert in the field of the assay and complete the assay putting together also all the literature and web sources used at the end. 
7. The final assay is stored locally as word document or something like that.

Research Pipeline Script
========================

This repository contains a Python-based research pipeline that leverages AI models, web scraping, and structured iterative refinement to produce comprehensive, in-depth essays on specified research topics.

Overview
--------

The pipeline integrates:

-   **Local AI models** (via Ollama)

-   **Web scraping** (DuckDuckGo)

-   **Iterative refinement** (AI-based reflection and revision)

-   **Structured logging** for tracking research progress

Features
--------

-   Generates an initial extensive answer to a research question.

-   Identifies gaps and formulates targeted search queries.

-   Performs web research to collect additional context.

-   Iteratively refines answers based on accumulated web content.

-   Outputs a polished Markdown essay with clearly cited sources.

Installation
------------

Clone this repository:

```
git clone <your-repo-url>
cd <repository-name>
```

Install dependencies using the provided `requirements.txt`:

```
pip install -r requirements.txt
```

Ensure you have an Ollama server running locally:

-   Install and run Ollama: <https://ollama.ai/>

-   Model used by default: `llama3.2`

Usage
-----

Run the script from your command line or in a Jupyter notebook:

```
python your_script_name.py
```

You will be prompted to enter your research topic. The pipeline will then:

1.  Generate an initial extensive answer.

2.  Identify gaps and create follow-up queries.

3.  Perform iterative web research and refinement.

4.  Output a comprehensive essay in Markdown format.

The final output and logs are saved as timestamped files in your working directory.

Configuration
-------------

You can modify the script's configuration parameters directly in the `Configuration` class within the script, including:

-   `ollama_base_url`: URL to your local Ollama server.

-   `local_llm`: Specify the local AI model.

-   `fetch_full_page`: Enable or disable fetching full webpage content.

-   `max_web_research_loops`: Number of research iterations.

-   `max_fetch_pages`: Number of search results to process each iteration.

-   `max_token_per_search`: Token limit per search for content management.

Output
------

The pipeline produces two main outputs:

-   **Markdown Essay**: `final_output_<timestamp>.md`

-   **Research Log**: `research_log_<timestamp>.txt`

The Markdown essay includes clearly referenced sources to ensure traceability and fact-checking.

Dependencies
------------

Key Python packages include:

-   `beautifulsoup4`

-   `duckduckgo_search`

-   `ollama`

-   `IPython`

(Complete dependencies listed in `requirements.txt`)

Contribution
------------

Contributions are welcome! Please fork the repository, create a branch for your feature or fix, and submit a pull request.

License
-------

This project is licensed under the MIT License - see the LICENSE file for details.
