import time
import requests
from bs4 import BeautifulSoup
from splinter import Browser
import unicodedata
import re

def fetch_remote_table(url):
    """
    Fetches a table from a remote URL and extracts team names and overall scores.

    This function sends a GET request to the specified URL, parses the HTML content,
    and extracts data from the first table found. It specifically looks for cells
    with classes 'team_name' and 'overall_score'.

    Args:
        url (str): The URL of the webpage containing the table to be fetched.

    Returns:
        dict: A dictionary where keys are team names and values are overall scores.
              Returns None if the table is not found or if the request fails.

    Raises:
        No exceptions are explicitly raised, but underlying libraries may raise exceptions
        for network errors or parsing issues.

    Example:
        >>> result = fetch_remote_table("https://picks.apawl.com")
        >>> print(result)
        {'Team A': '95', 'Team B': '87', ...}
    """
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table')
        
        if table:
            result = {}
            rows = table.find_all('tr')
            for row in rows:
                team_name_cell = row.find('td', class_='team_name')
                overall_score_cell = row.find('td', class_='overall_score')
                
                if team_name_cell and overall_score_cell:
                    team_name = team_name_cell.text.strip()
                    overall_score = int(overall_score_cell.text.strip())
                    result[team_name] = overall_score
            return result
        else:
            print("No table found in the HTML.")
            return None
    else:
        print(f"Failed to fetch the URL. Status code: {response.status_code}")
        return None


def fetch_espn_scores(group_id):
    """
    Fetches scores from ESPN's NFL Pigskin Pickem fantasy game for a specific group.

    This function uses a Chrome browser to navigate to the ESPN fantasy game page,
    extracts the score table, and calculates scores based on wins and losses.

    Args:
        group_id (str): The unique identifier for the ESPN fantasy group.

    Returns:
        dict: A dictionary where keys are player names and values are calculated scores.
              Returns None if the table is not found or if there's an error.

    Raises:
        No exceptions are explicitly raised, but underlying libraries may raise exceptions
        for browser automation or parsing issues.

    Note:
        - There's a 2-second delay to allow the page to load, which may need adjustment.
        - The score calculation is: wins - (2 * losses)

    Example:
        >>> result = fetch_espn_scores("c4857724-1309-444b-a767-7ffbf1bff57b")
        >>> print(result)
        {'Player1': 5, 'Player2': -3, ...}
    """
    with Browser("chrome", headless=False) as browser:
        results = {}

        browser.visit(f"https://fantasy.espn.com/games/nfl-pigskin-pickem-2024/group?id={group_id}")
        

        
        while True:
            # Wait for the page to load (adjust the time if needed)
            time.sleep(3)
            # Get the page source
            html = browser.html
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find the table that has "EntryTable" within its class strings
            table = soup.find('table')
            if table:
                rows = table.find_all('tr')
                for row in rows[1:]:  # Skip the header row
                    cells = row.find_all('td')
                    if cells:
                        # Extract relevant information from cells
                        # Adjust the indices based on the actual structure of your table
                        name = cells[1].a.text.strip()
                        score_str = cells[2].text.strip()
                        wins, losses = map(int, score_str.split('-'))
                        score = wins - 2 * losses
                        results[name] = score
            else:
                print("Table not found")
                return None
            
            # Check if there's a next button
            next_button = browser.find_by_css('.Pagination__Button--next:not(.Button--disabled)')
            
            if next_button:
                # Scroll to the next button
                browser.execute_script("arguments[0].scrollIntoView();", next_button._element)
                # Wait a short moment for the scroll to complete
                time.sleep(0.5)
                # Click the next button using JavaScript
                browser.execute_script("arguments[0].click();", next_button._element)
            else:
                # No more pages, exit the loop
                break
        return results

def compare_dictionaries(our_scoreboard, espn_site):
    normalized_our_scoreboard = {normalize_key(k): v for k, v in our_scoreboard.items()}
    normalized_espn_site = {normalize_key(k): v for k, v in espn_site.items()}

    if normalized_our_scoreboard == normalized_espn_site:
        print('Scoreboards match.')
        return True
    else:
        print("Scoreboards don't match. Differences:")
        all_keys = set(normalized_our_scoreboard.keys()) | set(normalized_espn_site.keys())
        for key in all_keys:
            if key not in normalized_our_scoreboard:
                print(f"'{key}' is in espn_site but not in our_scoreboard")
            elif key not in normalized_espn_site:
                print(f"'{key}' is in our_scoreboard but not in espn_site")
            elif normalized_our_scoreboard[key] != normalized_espn_site[key]:
                print(f"'{key}' has different values: our_scoreboard[{key}] = {normalized_our_scoreboard[key]}, espn_site[{key}] = {normalized_espn_site[key]}")
        return False

def normalize_key(key):
    # Replace various types of apostrophes and similar characters with a standard apostrophe
    key = re.sub(r'[''′`´]', "'", key)
    # Remove any remaining non-alphanumeric characters (except spaces and apostrophes)
    key = re.sub(r'[^a-zA-Z0-9\s\']', '', key)
    return key.lower()  # Convert to lowercase for case-insensitive comparison

def compare_dictionaries(our_scoreboard, espn_site):
    normalized_our_scoreboard = {normalize_key(k): v for k, v in our_scoreboard.items()}
    normalized_espn_site = {normalize_key(k): v for k, v in espn_site.items()}

    if normalized_our_scoreboard == normalized_espn_site:
        print('Dictionaries match.')
        return True
    else:
        print("Differences:")
        all_keys = set(normalized_our_scoreboard.keys()) | set(normalized_espn_site.keys())
        for key in all_keys:
            original_our_key = next((k for k in our_scoreboard if normalize_key(k) == key), None)
            original_espn_key = next((k for k in espn_site if normalize_key(k) == key), None)
            
            if key not in normalized_our_scoreboard:
                print(f"'{original_espn_key}' is in espn_site but not in our_scoreboard")
            elif key not in normalized_espn_site:
                print(f"'{original_our_key}' is in our_scoreboard but not in espn_site")
            elif normalized_our_scoreboard[key] != normalized_espn_site[key]:
                print(f"'{original_our_key}' (our_scoreboard) / '{original_espn_key}' (espn_site) has different values: "
                      f"our_scoreboard = {normalized_our_scoreboard[key]}, espn_site = {normalized_espn_site[key]}")
        return False

# Example usage:
remote_table = fetch_remote_table("https://picks.apawl.com")
espn_scores = fetch_espn_scores("c4857724-1309-444b-a767-7ffbf1bff57b")
# print(espn_scores)
compare_dictionaries(remote_table, espn_scores)