import os 
import re 
import random
import requests
from bs4 import BeautifulSoup
from googlesearch import search
from fuzzywuzzy import fuzz
from colorama import Fore, Style
import time
import json

# ========== CONFIGURATION ========== #
HUGGINGFACE_API_TOKEN = "hf_x"
HF_API_URL = "https://api-inference.huggingface.co/models/x"
HEADERS = {"Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}"}
MEMORY_FILE = "memory.json"
NUM_RESULTS = 10

# ========== HUGGING FACE LLM ========== #
def call_llm(prompt):
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 200, "temperature": 0.7}
    }
    response = requests.post(HF_API_URL, headers=HEADERS, json=payload)
    if response.status_code == 200:
        return response.json()[0]["generated_text"]
    else:
        print("[LLM ERROR]", response.status_code, response.text)
        return "LLM failed"

# ========== MEMORY SYSTEM ========== #
def load_memory():
    try:
        with open(MEMORY_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_memory(memory):
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memory, f, indent=2)

# ========== AGENTS ========== #
def generation_agent(topic):
    query = (
        f"{topic} site:arxiv.org OR site:nature.com OR "
        f"site:ncbi.nlm.nih.gov OR site:science.org OR site:sciencedaily.com OR "
        f"site:researchgate.net OR site:theconversation.com"
    )
    return list(search(query, num_results=NUM_RESULTS))

def scrape_content(url):
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
                )
            }
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        paragraphs = soup.find_all('p')
        text = " ".join([p.get_text() for p in paragraphs])
        
        cleaned = text.strip().replace("\\n", " ")
        cleaned = re.sub(r"(Sign up\s*Sign in\s*)+", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"(Home\s+Library\s+Stories\s+Stats\s+\w+\s+Follow\s*--\s*Listen\s*Share\s*)+", "", cleaned, flags=re.IGNORECASE)
        content = cleaned[:2000]

        title = soup.title.string if soup.title else url
        return title, content
    except:
        return url, ""

def reflection_agent(title, content, query):
    title_score = fuzz.partial_ratio(title.lower(), query.lower())
    content_score = fuzz.partial_ratio(content.lower(), query.lower())
    print(f"[Reflection Agent] Title: {title_score}, Content: {content_score}")
    return (title_score + content_score) / 2 >= 60


def simple_sent_tokenize(text):
    return re.split(r'(?<=[.!?])\s+', text)

def ranking_agent(summaries, topic):
    prompt = (
        f"You are a helpful AI research assistant.\n"
        f"Given the following summaries for the topic '{topic}',\n"
        f"choose the most informative one based on clarity and depth.\n"
        f"Reply as: Best Option: [number] and a one-line reason.\n\n"
    )
    for i, summary in enumerate(summaries):
        prompt += f"Option {i+1}: {summary}\n\n"

    llm_response = call_llm(prompt)
    
    match = re.search(r"Option\s*:?[\s]([1-9][0-9])", llm_response, re.IGNORECASE)
    if match:
        option_number = int(match.group(1))
        selected = option_number - 1 if 1 <= option_number <= len(summaries) else 0
    else:
        print("[Ranking Agent] Failed to parse LLM response. Defaulting to Option 1.")
        selected = 0

    lines = [line.strip() for line in llm_response.strip().splitlines()]
    summary_line = next((line for line in lines if re.search(r"Option\s*\d+", line, re.IGNORECASE)), "Best Option: 1 - Reason not found.")

    return summaries[selected], summary_line

def meta_review_agent(start_time, topic, output):
    duration = round(time.time() - start_time, 2)
    print(f"[Meta-review] Topic: {topic} | Time: {duration}s | Output length: {len(output)}")

# ========== SUPERVISOR ========== #
def supervisor(topic):
    memory = load_memory()
    topics = [topic]

    for topic in topics:
        if topic in memory:
            best_paper = memory[topic]["best_paper"]
            llm_reason = memory[topic]["llm_reason"]

            summary_sentences = simple_sent_tokenize(best_paper["summary"])
            trimmed_summary = " ".join(summary_sentences[:2])

            match = re.search(r"Option\s*\d+\s*:\s*(.*)", llm_reason)
            reason = match.group(1).strip() if match else "No reason found."

            return best_paper["link"], trimmed_summary, reason

        start = time.time()
        urls = generation_agent(topic)

        papers = []
        for url in urls:
            time.sleep(random.uniform(1, 3))
            title, content = scrape_content(url)
            if not content:
                continue

            score = reflection_agent(title, content, topic)
            if score:
                papers.append({
                    "title": title, 
                    "summary": content,
                    "link": url
                })

        if not papers:
            return None, "No relevant papers found.", ""

        summaries = [paper['summary'] for paper in papers[:3]]
        best_summary, llm_reason = ranking_agent(summaries, topic)
        selected_paper = papers[summaries.index(best_summary)]

        summary_sentences = simple_sent_tokenize(selected_paper["summary"])
        trimmed_summary = " ".join(summary_sentences[:2])

        match = re.search(r"Option\s*\d+\s*:\s*(.*)", llm_reason)
        reason = match.group(1).strip() if match else "No reason found."

        memory[topic] = {
            "best_paper": selected_paper,
            "llm_reason": llm_reason
        }

        save_memory(memory)
        meta_review_agent(start, topic, llm_reason)

        return selected_paper["link"], trimmed_summary, reason


if __name__ == "__main__":
    topic = input("Enter your research topic: ")
    supervisor(topic)