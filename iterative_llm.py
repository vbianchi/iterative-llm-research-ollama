import json
import re
import time
import urllib.request
import datetime
from typing import Dict, List
from bs4 import BeautifulSoup
from ollama import chat, ChatResponse
from IPython.display import display, Markdown

# --- Logging Setup ---
def clear_log(filename: str) -> None:
    """Clear the log file."""
    with open(filename, "w", encoding="utf-8") as f:
        f.write("")

def log(message: str, filename: str) -> None:
    """Append a message to the log file."""
    with open(filename, "a", encoding="utf-8") as f:
        f.write(message + "\n")

# --- Helper: Remove <THINK> Tags ---
def remove_think_tags(text: str) -> str:
    """
    Remove any text enclosed in <THINK>...</THINK> tags.
    The regex is case-insensitive.
    """
    return re.sub(r"<\s*THINK\s*>.*?<\s*/\s*THINK\s*>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()

# --- Prompt Baselines ---
INITIAL_RESPONSE_PROMPT = (
    "You are an expert on the topic {research_topic}. Provide an extensive, detailed, and comprehensive answer "
    "to the research question. In your answer, highlight any areas or gaps that might require further exploration."
)

QUERY_WRITER_INSTRUCTIONS = (
    "Your goal is to generate a targeted web search query to address gaps in your research answer.\n"
    "The research topic is:\n<TOPIC>\n{research_topic}\n</TOPIC>\n\n"
    "Based on the gaps identified in your answer, generate a JSON object with the following keys:\n"
    '   - "query": "The search query string."\n'
    '   - "aspect": "The aspect of the topic being addressed by this query."\n'
    '   - "rationale": "Why this query will help fill the gap."\n'
    "Return only the JSON object."
)

REFLECTION_INSTRUCTIONS = (
    "You are an expert research assistant reviewing the updated answer on the topic \"{research_topic}\".\n"
    "Below is the updated answer. Identify any remaining knowledge gaps and propose a follow-up search query "
    "that addresses these gaps while remaining aligned with the original research question.\n\n"
    "Updated Answer:\n-------------------------\n{updated_answer}\n-------------------------\n\n"
    "Return a JSON object with the following keys:\n"
    '   - "knowledge_gap": "A description of what is missing or unclear."\n'
    '   - "follow_up_query": "A specific follow-up search query to address the gap."\n'
    "Return only the JSON object."
)

FINAL_ESSAY_INSTRUCTIONS = (
    "You are an expert on the topic {research_topic}. Based on the research results provided below, "
    "write a comprehensive, long-form essay that addresses all key points in a captivating and rigorous manner.\n"
    "Your essay should:\n"
    "1. Present a captivating narrative.\n"
    "2. Be rigorous and factual, with every claim supported by the research.\n"
    "3. Clearly integrate all key points and arguments.\n"
    "Format the final output in Markdown.\n\n"
    "Research Results:\n{research_results}"
)

# --- Helper: Format Source URLs ---
def format_source_urls(text: str) -> str:
    """
    Extract lines starting with "URL:" from the given text, remove the "URL:" prefix,
    and return a string with each URL on a new line preceded by an incremental number.
    """
    lines = text.splitlines()
    urls = [line.strip()[len("URL:"):].strip() for line in lines if line.strip().startswith("URL:")]
    return "\n".join(f"{i+1}. {url}" for i, url in enumerate(urls))

# --- Web Search Functions ---
def duckduckgo_search(query: str, max_results: int = 3, fetch_full_page: bool = False) -> Dict[str, List[Dict[str, str]]]:
    """
    Perform a DuckDuckGo search for the given query.
    Optionally fetch full page content.
    """
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            search_results = list(ddgs.text(query, max_results=max_results))
            for r in search_results:
                url = r.get('href')
                title = r.get('title')
                content = r.get('body')
                if not all([url, title, content]):
                    log(f"Warning: Incomplete result from DuckDuckGo: {r}", LOG_FILE)
                    continue
                raw_content = content
                if fetch_full_page:
                    try:
                        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
                        response = urllib.request.urlopen(req)
                        html = response.read().decode('utf-8', errors='replace')
                        raw_content = BeautifulSoup(html, 'html.parser').get_text()
                    except Exception as e:
                        log(f"Warning: Failed to fetch full page content for {url}: {str(e)}", LOG_FILE)
                results.append({
                    "title": title,
                    "url": url,
                    "content": content,
                    "raw_content": raw_content
                })
        return {"results": results}
    except Exception as e:
        log(f"Error in DuckDuckGo search: {str(e)}", LOG_FILE)
        return {"results": []}

def deduplicate_and_format_sources(search_response, max_tokens_per_source: int, include_raw_content: bool = False) -> str:
    """
    Deduplicate search results (by URL) and format them as a structured string.
    Limits raw_content to roughly max_tokens_per_source tokens.
    """
    if isinstance(search_response, dict):
        sources_list = search_response.get('results', [])
    elif isinstance(search_response, list):
        sources_list = []
        for resp in search_response:
            if isinstance(resp, dict) and 'results' in resp:
                sources_list.extend(resp['results'])
            else:
                sources_list.extend(resp)
    else:
        raise ValueError("Input must be a dict with 'results' or a list of search results")
    
    unique_sources = {}
    for source in sources_list:
        url = source.get('url')
        if url and url not in unique_sources:
            unique_sources[url] = source

    formatted_text = "Sources:\n\n"
    for i, source in enumerate(unique_sources.values(), 1):
        formatted_text += f"Source {i} - {source.get('title', 'No Title')}:\n"
        formatted_text += "===\n"
        formatted_text += f"URL: {source.get('url', 'No URL')}\n"
        formatted_text += "===\n"
        formatted_text += f"Content: {source.get('content', 'No content available')}\n"
        formatted_text += "===\n"
        if include_raw_content:
            char_limit = max_tokens_per_source * 4
            raw_content = source.get('raw_content', '')
            if not raw_content:
                log(f"Warning: No raw_content found for source {source.get('url')}", LOG_FILE)
            if len(raw_content) > char_limit:
                raw_content = raw_content[:char_limit] + "... [truncated]"
            formatted_text += f"Full source content limited to {max_tokens_per_source} tokens: {raw_content}\n\n"
        else:
            formatted_text += "\n"
    return formatted_text.strip()

def consolidate_sources(state, max_tokens_per_source: int = 1000, include_raw_content: bool = True) -> str:
    """
    Consolidate all raw search results (flattened) into one deduplicated string.
    """
    flattened = [item for sublist in state.get("raw_sources", []) for item in sublist]
    return deduplicate_and_format_sources({"results": flattened}, max_tokens_per_source, include_raw_content)

# --- Configuration & State Management ---
class Configuration:
    def __init__(self, ollama_base_url: str, local_llm: str, fetch_full_page: bool,
                 max_web_research_loops: int, max_fetch_pages: int, max_token_per_search: int):
        self.ollama_base_url = ollama_base_url
        self.local_llm = local_llm
        self.fetch_full_page = fetch_full_page
        self.max_web_research_loops = max_web_research_loops
        self.max_fetch_pages = max_fetch_pages
        self.max_token_per_search = max_token_per_search

def initialize_state(research_topic: str) -> dict:
    """
    Initialize the research state with the given topic.
    """
    return {
        "research_topic": research_topic,
        "initial_response": "",       # The original extensive answer.
        "running_response": "",       # The updated answer.
        "research_loop_count": 0,
        "raw_sources": [],            # Store raw search results.
        "accumulated_results": "",    # Accumulate formatted web research results.
        "search_query": research_topic
    }

# --- LLM Integration Functions ---
def fix_invalid_json(json_str: str) -> str:
    """
    Attempt to fix common JSON formatting issues.
    """
    pattern = r'("rationale":\s*)([^"].*?)([,\}\n])'
    def replacer(match):
        prefix, value, suffix = match.group(1), match.group(2).strip(), match.group(3)
        return f'{prefix}"{value}"{suffix}'
    return re.sub(pattern, replacer, json_str, flags=re.DOTALL)

def generate_initial_response(state: dict, config: Configuration) -> str:
    """
    Generate an extensive initial answer for the research topic.
    The answer should also indicate potential gaps for further research.
    """
    prompt = INITIAL_RESPONSE_PROMPT.format(research_topic=state["research_topic"])
    message = {"role": "user", "content": prompt}
    response: ChatResponse = chat(model=config.local_llm, messages=[message])
    initial_response = remove_think_tags(response.message.content.strip())
    state["initial_response"] = initial_response
    state["running_response"] = initial_response  # Set baseline.
    state["accumulated_results"] += initial_response + "\n\n"
    log("Initial response: " + initial_response, LOG_FILE)
    return initial_response

def generate_query(state: dict, config: Configuration) -> str:
    """
    Generate a targeted web search query using the LLM.
    Expects a JSON response with keys 'query', 'aspect', and 'rationale'.
    """
    prompt = QUERY_WRITER_INSTRUCTIONS.format(research_topic=state["research_topic"])
    message = {
        "role": "user",
        "content": prompt + "\nGenerate a targeted web search query as a JSON object with keys 'query', 'aspect', and 'rationale'."
    }
    response: ChatResponse = chat(model=config.local_llm, messages=[message])
    raw_content = remove_think_tags(response.message.content.strip())
    log("Raw query response: " + raw_content, LOG_FILE)
    json_match = re.search(r"\{.*\}", raw_content, re.DOTALL)
    json_str = json_match.group(0) if json_match else raw_content
    try:
        result = json.loads(json_str)
        query = result.get("query")
    except Exception as e:
        log(f"Error parsing query response: {e}", LOG_FILE)
        fixed_json_str = fix_invalid_json(json_str)
        log("Fixed JSON string: " + fixed_json_str, LOG_FILE)
        try:
            result = json.loads(fixed_json_str)
            query = result.get("query")
        except Exception as e2:
            log(f"Error parsing fixed JSON: {e2}", LOG_FILE)
            query = state["research_topic"]
    return query

def perform_web_research(state: dict, config: Configuration) -> str:
    """
    Perform a web search using the current query, store raw results, and append formatted results.
    """
    search_query = state["search_query"]
    log(f"Performing web research with query: {search_query}", LOG_FILE)
    search_results = duckduckgo_search(search_query, max_results=config.max_fetch_pages, fetch_full_page=config.fetch_full_page)
    state.setdefault("raw_sources", []).append(search_results.get("results", []))
    formatted_sources = deduplicate_and_format_sources(search_results, max_tokens_per_source=config.max_token_per_search, include_raw_content=True)
    state["accumulated_results"] += formatted_sources + "\n\n"
    return formatted_sources

def revise_response(state: dict, config: Configuration) -> str:
    """
    Revise the current answer by integrating the accumulated research results.
    Preserve core content while addressing any gaps.
    """
    current_response = state["running_response"]
    new_research = state["accumulated_results"]
    prompt = f"""
You are an expert on the topic {state['research_topic']}.
Below is your current answer:
-------------------------
{current_response}
-------------------------
And here are the accumulated research results:
-------------------------
{new_research}
-------------------------
Please revise your answer to integrate the new information and address any gaps.
Return your revised answer as plain text.
    """
    message = {"role": "user", "content": prompt}
    response: ChatResponse = chat(model=config.local_llm, messages=[message])
    revised_response = remove_think_tags(response.message.content.strip())
    state["running_response"] = revised_response
    log("Revised response: " + revised_response, LOG_FILE)
    return revised_response

def reflect_on_results(state: dict, config: Configuration) -> str:
    """
    Reflect on the updated answer to generate a follow-up query.
    Expects a JSON response with keys 'knowledge_gap' and 'follow_up_query'.
    """
    prompt = REFLECTION_INSTRUCTIONS.format(research_topic=state["research_topic"], updated_answer=state["running_response"])
    prompt += "\n\nRevised Answer:\n" + state["running_response"]
    prompt += "\n\nIdentify a knowledge gap and propose a follow-up query for a web search as a JSON object with keys 'knowledge_gap' and 'follow_up_query':"
    message = {"role": "user", "content": prompt}
    response: ChatResponse = chat(model=config.local_llm, messages=[message])
    raw_content = remove_think_tags(response.message.content.strip())
    log("Raw reflection response: " + raw_content, LOG_FILE)
    json_match = re.search(r"\{.*\}", raw_content, re.DOTALL)
    json_str = json_match.group(0) if json_match else raw_content
    try:
        result = json.loads(json_str)
        follow_up_query = result.get("follow_up_query")
        if not isinstance(follow_up_query, str):
            follow_up_query = json.dumps(follow_up_query)
    except Exception as e:
        log(f"Error parsing reflection response: {e}", LOG_FILE)
        follow_up_query = raw_content
    state["search_query"] = follow_up_query
    return follow_up_query

def generate_final_essay(state: dict, config: Configuration) -> str:
    """
    Generate the final essay in Markdown based on the updated answer.
    Append a "Sources" section containing URLs extracted from the accumulated research.
    """
    final_response = state["running_response"]
    prompt = FINAL_ESSAY_INSTRUCTIONS.format(research_topic=state["research_topic"], research_results=final_response)
    message = {"role": "user", "content": prompt}
    response: ChatResponse = chat(model=config.local_llm, messages=[message])
    final_essay = remove_think_tags(response.message.content.strip())
    formatted_urls = format_source_urls(state["accumulated_results"])
    sources_section = f"\n\n### Sources:\n{formatted_urls}"
    final_output = final_essay + sources_section
    return final_output

def generate_styled_output(state: dict, config: Configuration) -> str:
    """
    Generate the final styled Markdown output.
    """
    return generate_final_essay(state, config)

# --- Main Research Pipeline ---
def research_pipeline() -> None:
    # Create timestamped filenames.
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"research_log_{timestamp}.txt"
    final_output_filename = f"final_output_{timestamp}.md"
    
    global LOG_FILE
    LOG_FILE = log_filename
    clear_log(LOG_FILE)
    
    config = Configuration(
        ollama_base_url="http://localhost:11434",  # Your Ollama URL
        local_llm="gemma3",                      # Default LLM is "llama3.2"
        fetch_full_page=True,                      # Fetch full page content if needed
        max_web_research_loops=20,                  # Number of research iterations
        max_fetch_pages=5,                         # Number of pages to fetch per search
        max_token_per_search=4000                  # Token limit per search processing
    )
    
    research_topic = input("Enter your research topic: ").strip()
    state = initialize_state(research_topic)
    
    # Step 1: Generate an extensive initial answer.
    initial_response = generate_initial_response(state, config)
    print("\nInitial Answer:")
    print(initial_response)
    
    # Step 2: Generate an initial query for web research.
    generated_query = generate_query(state, config)
    print(f"\nGenerated Query: {generated_query}")
    state["search_query"] = generated_query if generated_query else research_topic
    
    # Step 3: Iteratively perform web research, revise answer, and reflect.
    for i in range(config.max_web_research_loops):
        print(f"\n--- Research Iteration {i+1} ---")
        _ = perform_web_research(state, config)
        print("  >> Web sources gathered.")
        revised_response = revise_response(state, config)
        print("  >> Revised answer updated.")
        follow_up = reflect_on_results(state, config)
        print("  >> Next query identified: " + follow_up)
        state["research_loop_count"] += 1
        time.sleep(1)
    
    # Step 4: Generate the final essay with Sources section.
    final_markdown = generate_styled_output(state, config)
    print("\n--- Final Summary (Markdown) ---\n")
    display(Markdown(final_markdown))
    
    with open(final_output_filename, "w", encoding="utf-8") as f:
        f.write(final_markdown)
    
    log("\n--- Final Summary (Markdown) ---\n" + final_markdown, LOG_FILE)

if __name__ == "__main__":
    research_pipeline()
