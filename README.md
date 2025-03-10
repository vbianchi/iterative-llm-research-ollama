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
