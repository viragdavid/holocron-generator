### WOOKIEPEDIA SCRAPER ###
import requests
import random
import json
import bs4
import urllib.parse
import re
import os
from collections import defaultdict

# Generated articles are tracked here
TRACKING_ARTICLE_FILE = "../data/generated_articles.log"
BASE_ARTICLE_DIRECTORY = "../data/generated_articles" # Base directory for all saved articles

# --- CATEGORY DEFINITION AND FILTERING SECTIONS ---

# 1. CATEGORIES TO ALWAYS EXCLUDE from being processed/saved, regardless of source
#    These are often meta-categories, real-world, or irrelevant technical tags.
EXCLUDE_CATEGORIES_FOR_ANY_USE = {
    "Real-world people", "Real-world media", "Disambiguation pages", "Dates",
    "Community content", "Wookieepedia", "Wiki", "Articles with unpopulated pronoun parameters", 
    "Articles that use DPL", "Articles with incorrect canonical link",
    "Articles with an inconsistent canonical status",
    "Articles with broken file links", "Articles with dead external links",
    "Articles with information from unknown sources"
}

# 2. CATEGORIES TO AVOID USING AS FOLDER NAMES (too general or internal wiki-maintenance)
#    These categories might be on a page, but are not specific or descriptive or just too general.
AVOID_FOLDER_CATEGORIES = {
    "Articles needing illustration", "Articles with conjectural titles", "Articles with gameplay alternatives",
    "Archiveurl usages with non-Wayback URLs", "Canon articles", "Legends articles", "Canon articles with Legends counterparts"
}
# --- END CATEGORY DEFINITION AND FILTERING SECTIONS ---

# --- ARTICLE PROCESSING FUNCTIONS ---

# 1. Function to get previously generated titles from the tracking file
def get_previously_generated_titles(TRACKING_ARTICLE_FILE):
    """Reads the tracking file and returns a set of titles that have already been generated."""
    if not os.path.exists(TRACKING_ARTICLE_FILE):
        return set()
    with open(TRACKING_ARTICLE_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f)

# 2. Function to log a newly generated title
def log_generated_title(title, TRACKING_ARTICLE_FILE):
    """Appends a new title to the tracking file."""
    with open(TRACKING_ARTICLE_FILE, 'a', encoding='utf-8') as f:
        f.write(title + '\n')

# 3. Function to save the article content in a structured, token-efficient format
def save_article_to_file(title, parsed_data, image_urls, category_name="Uncategorized"):
    """Saves the structured, token-efficient article content to a text file in a category-specific folder."""
    
    # Sanitize category_name to be safe for a directory name
    sanitized_category_name = re.sub(r'[\\/*?:"<>|]', "", category_name).strip()
    if not sanitized_category_name: # Fallback if sanitization results in an empty string
        sanitized_category_name = "Uncategorized"

    # Create the category directory if it doesn't exist
    target_directory = os.path.join(BASE_ARTICLE_DIRECTORY, sanitized_category_name)
    os.makedirs(target_directory, exist_ok=True)

    sanitized_title = re.sub(r'[\\/*?:"<>|]', "", title.replace('/', '_'))
    filename = os.path.join(target_directory, f"{sanitized_title}.txt")
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"Title: {title}\n")

        # Write each content section from the parsed data
        for section, text in parsed_data['content_sections'].items():
            f.write(f"{section}: {text}\n")
        
        # Write the compacted table data
        if parsed_data['infobox_string']:
            f.write(f"Table: {parsed_data['infobox_string']}\n")
            
        # Write the comma-separated appearances
        if parsed_data['appearances']:
            appearances_line = ", ".join(parsed_data['appearances'])
            f.write(f"Appearances: {appearances_line}\n")
            
        # Write the comma-separated image URLs
        if image_urls:
            images_line = ", ".join(image_urls)
            f.write(f"Images: {images_line}\n")
            
    print(f"Article content saved to '{filename}' in AI-friendly format.")

# 4. Function to get a random title from Wookieepedia, checking against the tracking file and defined exclusion categories
def get_random_title(TRACKING_ARTICLE_FILE, max_attempts=30):
    """Gets a random title, checking against the tracking file and defined exclusion categories."""
    url = "https://starwars.fandom.com/api.php"
    generated_titles = get_previously_generated_titles(TRACKING_ARTICLE_FILE)
    print(f"Loaded {len(generated_titles)} previously generated titles.")
    
    for attempt in range(max_attempts):
        print(f"\nAttempt {attempt + 1}/{max_attempts} to find a new random article...")
        params = {"action": "query", "format": "json", "list": "random", "rnnamespace": 0, "rnlimit": 1}
        res = requests.get(url, params=params).json()
        random_title = res['query']['random'][0]['title']
        
        if random_title in generated_titles:
            print(f"'{random_title}' has already been generated. Skipping.")
            continue
        
        try:
            # Fetch categories for filtering
            params = {"action": "query", "format": "json", "titles": random_title, "prop": "categories", "cllimit": "max"}
            category_check_res = requests.get(url, params=params).json()
            page = next(iter(category_check_res["query"]["pages"].values()))
            
            page_categories = set()
            if 'categories' in page:
                page_categories = {cat['title'].replace("Category:", "") for cat in page['categories']}
                
            # Check for exclusion categories (using the centralized EXCLUDE_CATEGORIES_FOR_ANY_USE)
            if not page_categories.isdisjoint(EXCLUDE_CATEGORIES_FOR_ANY_USE):
                print(f"'{random_title}' is in an excluded category ({page_categories.intersection(EXCLUDE_CATEGORIES_FOR_ANY_USE)}). Skipping.")
                continue

            encoded_title = urllib.parse.quote(random_title.replace(' ', '_'))
            print("Found a new, valid random article URL:", f"https://starwars.fandom.com/wiki/{encoded_title}")
            
            return random_title, page_categories
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}. Skipping attempt.")
            continue
    return None, set() # Return None and an empty set if no title is found

# 5. Function to get all page data, including images and structured content
def get_article_content(title):
    """Gets all page data and returns it in a structured dictionary."""
    url = "https://starwars.fandom.com/api.php"
    params = {"action": "query", "format": "json", "prop": "images", "titles": title}
    res = requests.get(url, params=params).json()
    page = next(iter(res["query"]["pages"].values()))
    
    parsed_data = get_summary_from_html(title)
    
    return {
        "title": title,
        "parsed_data": parsed_data,
        "images": page.get("images", [])
    }

# 6. Function to filter out images based on specific keywords
# Todo: This functon doesnt work always properly, it should be improved
def filter_images(image_titles):
    exclude_keywords = [
        "logo", "banner", "icon", "question", "cite", "premium", "gotocanon", 
        "gotolegends", "swcustom", "tab-", "onacanonarticle", "onalegendsarticle", 
        "blue-exclamation-mark", "starwars-databank", "food-stub", "bobawhere", "char-stub",
        "falactic_senate", "swtor_mini", "onanoncanonarticle", "swajsmall", "wizardsofthecoast",
        "wiki-shrinkable", "lego", "military-stub", "SWTOR_mini", "kdy", "swinsider", "SWInsider",
        "stub", "planet-stub", "Planet-stub"
    ]
    filtered = []
    for image in image_titles:
        title = image['title'].lower()
        if not any(keyword in title for keyword in exclude_keywords):
            filtered.append(image)
    return filtered

# 7. Function to get image URLs from the filtered image titles
def get_image_urls(image_titles):
    urls = []
    for image in image_titles:
        title = image['title']
        url = "https://starwars.fandom.com/api.php"
        params = {"action": "query", "format": "json", "titles": title, "prop": "imageinfo", "iiprop": "url"}
        res = requests.get(url, params=params).json()
        page = next(iter(res['query']['pages'].values()))
        if 'imageinfo' in page:
            urls.append(page['imageinfo'][0]['url'])
    return urls

# 8. Function to scrape a Wookieepedia page and return structured content
def get_summary_from_html(title):
    """
    Scrapes a Wookieepedia page and returns a structured dictionary of its content.
    """
    url = f"https://starwars.fandom.com/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
    
    try:
        res = requests.get(url)
        res.raise_for_status()
        soup = bs4.BeautifulSoup(res.text, 'html.parser')
        
        # --- Data Extraction into Intermediate Structures ---
        infobox_data = defaultdict(list)
        infobox = soup.find('aside', class_='portable-infobox')
        if infobox:
            current_section = infobox.find('h2', class_='pi-title').get_text(strip=True) if infobox.find('h2', 'pi-title') else "General"
            for item in infobox.find_all(['h2', 'div'], class_=['pi-header', 'pi-data']):
                if 'pi-header' in item.get('class', []):
                    current_section = item.get_text(strip=True)
                elif 'pi-data' in item.get('class', []):
                    label_el = item.find('h3', class_='pi-data-label')
                    value_el = item.find('div', class_='pi-data-value')
                    if label_el and value_el:
                        for sup in value_el.find_all('sup', class_='reference'): sup.decompose()
                        key = label_el.get_text(strip=True)
                        value = ' '.join(value_el.get_text(separator=' ', strip=True).split())
                        infobox_data[current_section].append(f"{key}: {value}")
            infobox.decompose()

        # --- Content Section Parsing ---
        content_sections = defaultdict(list)
        appearances = []
        current_section_key = 'Main' # For text before the first header
        content_div = soup.find('div', class_='mw-parser-output')
        if content_div:
            parsing_appearances = False
            for element in content_div.find_all(['h2', 'h3', 'p', 'div', 'ul'], recursive=False):
                if element.name in ['h2', 'h3']:
                    headline_span = element.find('span', class_='mw-headline')
                    if not headline_span: continue
                    headline_text = headline_span.get_text(strip=True)
                    stop_keywords = ["Sources", "Notes and references", "See also", "External links"]
                    if any(keyword in headline_text for keyword in stop_keywords): break
                    parsing_appearances = "Appearances" in headline_text
                    if not parsing_appearances:
                        current_section_key = headline_text
                elif parsing_appearances and element.name in ['div', 'ul']:
                    for li in element.find_all('li'):
                        raw_text = li.get_text(strip=True)
                        cleaned_text = re.sub(r'\s*\([^)]*\)', '', raw_text).strip()
                        if cleaned_text: appearances.append(cleaned_text)
                elif not parsing_appearances and element.name == 'p':
                    for sup in element.find_all('sup', class_='reference'): sup.decompose()
                    text = element.get_text(separator=' ', strip=True)
                    if text: content_sections[current_section_key].append(text)

        # --- Final Formatting into Token-Efficient Strings ---
        final_sections = {key: " ".join(value) for key, value in content_sections.items()}
        
        infobox_string_parts = []
        for section, kv_pairs in infobox_data.items():
            pairs_str = "; ".join(kv_pairs)
            infobox_string_parts.append(f"{section} | {pairs_str}")
        infobox_final_str = " | ".join(infobox_string_parts)
        
        return {
            "infobox_string": infobox_final_str,
            "content_sections": final_sections,
            "appearances": appearances
        }
    except Exception as e:
        return {"infobox_string": "", "content_sections": {"Error": str(e)}, "appearances": []}
# --- END ARTICLE PROCESSING FUNCTIONS ---

# --- Main Execution ---
if __name__ == "__main__":
    
    # Create the base saving directory if it doesn't exist
    os.makedirs(BASE_ARTICLE_DIRECTORY, exist_ok=True)
    
    # Always try to get a random title
    title, categories = get_random_title(TRACKING_ARTICLE_FILE)
    
    if title:
        page_data = get_article_content(title)
        
        if "Error" in page_data["parsed_data"]["content_sections"]:
            print(f"Could not process '{title}'. Reason: {page_data['parsed_data']['content_sections']['Error']}")
        else:
            filtered_images = filter_images(page_data["images"])
            image_urls = get_image_urls(filtered_images)
            
            chosen_category_for_folder = "Uncategorized" # Default fallback

            # Combine all exclusion sets for checking against potential folder names
            all_avoid_categories_for_folder_name = AVOID_FOLDER_CATEGORIES.union(EXCLUDE_CATEGORIES_FOR_ANY_USE)
            
            # Convert categories set to a sorted list to ensure deterministic "first" tag
            sorted_page_categories = sorted(list(categories))
            
            # Iterate through the page's categories and pick the first suitable one for the folder name
            for cat in sorted_page_categories:
                # Check if the category is suitable (not in any exclusion/avoid list, and not a generic keyword)
                if cat not in all_avoid_categories_for_folder_name and \
                   not any(keyword in cat.lower() for keyword in ["real-world", "disambiguation", "date", "fictional"]):
                    chosen_category_for_folder = cat
                    break # Use this category and stop searching

            # Save the structured data to the file
            save_article_to_file(
                page_data["title"], 
                page_data["parsed_data"], 
                image_urls,
                category_name=chosen_category_for_folder # Pass the determined category
            )
            
            log_generated_title(page_data["title"], TRACKING_ARTICLE_FILE)
            print(f"\nProcess complete. '{title}' has been saved and logged in the '{chosen_category_for_folder}' folder.")
    else:
        print("\nCould not find a new article to process after multiple attempts.")