import json
import re
import random
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

MEMORY_FILE = "research_memory.json"

# Load saved research data
def load_memory():
    try:
        with open(MEMORY_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

# Save research data
def save_memory(data):
    with open(MEMORY_FILE, "w") as file:
        json.dump(data, file, indent=4)

# Tokenize a title by removing punctuation and lowercasing
def tokenize_title(title):
    return set(re.sub(r"[^\w\s]", "", title.lower()).split())

# Check if a title matches the search query based on a threshold
def is_match(input_title, paper_title, threshold=10):
    input_tokens = tokenize_title(input_title)
    paper_tokens = tokenize_title(paper_title)
    common_words = input_tokens.intersection(paper_tokens)
    match_percentage = (len(common_words) / len(input_tokens)) * 100 if input_tokens else 0
    return match_percentage >= threshold, match_percentage

# Main supervisor agent that runs all other agents
def supervisor_agent(search_query):
    print(f"\n🔶 Supervisor Agent: Managing Research on '{search_query}'...")
    
    memory = load_memory()
    iteration = 1
    
    while iteration <= 3:
        print(f"\n🔄 Iteration {iteration}...")
        papers = generation_agent(search_query)
        feasible_papers = reflection_agent(papers, search_query)
        ranked_papers = ranking_agent(feasible_papers, search_query)
        improved_papers = evolution_agent(ranked_papers)
        final_papers = proximity_agent(improved_papers)
        iteration += 1
    
    memory[search_query] = final_papers[:10]
    save_memory(memory)
    meta_review_agent(final_papers)
    
    print("\n✅ Final Optimized Papers:")
    for i, paper in enumerate(final_papers[:10], 1):
        print(f"{i}. {paper['title']}\n   🔗 {paper['link']}\n   📝 Abstract: {paper['abstract']}\n   📊 Score: {paper['score']} - {paper['ranking_reason']}")
    
    return final_papers[:10]

# Web scraping agent that retrieves research papers
def generation_agent(search_query):
    print(f"\n🔹 Generation Agent: Fetching Papers for '{search_query}'...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    websites = {
        "Google Scholar": {
            "url": f"https://scholar.google.com/scholar?q={search_query.replace(' ', '+')}",
            "title_xpath": "//h3[@class='gs_rt']/a",
            "link_xpath": "//h3[@class='gs_rt']/a",
            "abstract_xpath": "//div[@class='gs_rs']"
        },
        "CORE (Research Papers)": {
            "url": f"https://core.ac.uk/search?q={search_query.replace(' ', '+')}",
            "title_xpath": "//div[contains(@class, 'search-result')]//h3/a",
            "link_xpath": "//div[contains(@class, 'search-result')]//h3/a",
            "abstract_xpath": "//div[contains(@class, 'search-result')]//p"
        }
    }

    data_list = []
    for site, details in websites.items():
        driver.get(details["url"])
        try:
            # Dynamically wait for the page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, details["title_xpath"]))
            )
            titles = driver.find_elements(By.XPATH, details["title_xpath"])
            links = driver.find_elements(By.XPATH, details["link_xpath"])
            abstracts = driver.find_elements(By.XPATH, details["abstract_xpath"])

            for i in range(min(len(titles), len(links))):
                abstract_text = abstracts[i].text.strip() if i < len(abstracts) else "No abstract available"
                data_list.append({
                    "site": site,
                    "title": titles[i].text.strip(),
                    "link": links[i].get_attribute("href"),
                    "abstract": abstract_text
                })
        except TimeoutException:
            print(f"⚠️ Timeout: No results loaded from {site} within 10 seconds.")

    driver.quit()
    return data_list

# Filters papers based on relevance to search query
def reflection_agent(papers, search_query):
    return [paper for paper in papers if is_match(search_query, paper["title"])[0]]

# Ranks papers based on title and abstract match, scales score to 100
def ranking_agent(papers, search_query):
    scored_papers = []
    for paper in papers:
        base_score = random.randint(50, 100)  # Base score between 50-100
        abstract_match = is_match(search_query, paper.get("abstract", ""), threshold=50)[1]
        unscaled_score = base_score + int(abstract_match / 2)  # Adjust based on abstract match
        scaled_score = (unscaled_score / 150) * 100  # Normalize to 100 scale
        ranking_reason = f"Base Score: {base_score}, Abstract Match: {abstract_match}%, Scaled Score: {scaled_score:.1f}"
        paper["score"] = round(scaled_score)
        paper["ranking_reason"] = ranking_reason
        scored_papers.append(paper)

    scored_papers = sorted(scored_papers, key=lambda x: x["score"], reverse=True)[:5]
    print("\n🔹 Ranking Details:")
    for paper in scored_papers:
        print(f"📜 {paper['title']} - {paper['ranking_reason']}")
    return scored_papers

# Selects the top 5 most relevant papers
def evolution_agent(papers):
    return papers[:5] if len(papers) > 5 else papers

# Placeholder function for further filtering (if needed)
def proximity_agent(papers):
    return papers

# Provides feedback on the quality of retrieved research papers
def meta_review_agent(papers):
    print("\n🔹 Meta-Review Agent: Analysis & Recommendations...")
    if not papers:
        print("⚠️ No high-quality papers found. Consider refining your query.")
    elif all(paper["score"] < 70 for paper in papers):
        print("⚠️ Papers retrieved have moderate relevance. Try a more specific search term.")
    else:
        print("✅ Papers successfully ranked with strong relevance.")

# Run the research system
search_query = input("Enter your research topic: ").strip()
supervisor_agent(search_query)