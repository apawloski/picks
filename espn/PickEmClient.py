from bs4 import BeautifulSoup
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    TimeoutException,
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from splinter import Browser
from splinter.exceptions import ElementDoesNotExist
import logging
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from espn.models import Team, Pick

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


class PickEmClient:
    def __init__(self, group_id):
        self.group_id = group_id
        self.teams = {}  # Maps team name to Team object
        self.teams_lock = Lock()  # For thread-safe access to self.teams
        self.browser = None
        self.wait = None

    def run(self, week=None):
        """
        Main method to orchestrate the scraping and parsing process.
        """
        try:
            with Browser("chrome", headless=True) as browser:
                self.browser = browser
                self.wait = WebDriverWait(self.browser.driver, 20)
                self._navigate_to_group_picks()
                weeks_to_soups = self._scrape_all_weeks(week=week)
                self._parse_soups(weeks_to_soups)
        finally:
            self.browser = None
            self.wait = None

    def _navigate_to_group_picks(self):
        """
        Navigates to the group picks page.
        """
        url = f"https://fantasy.espn.com/games/nfl-pigskin-pickem-2025/group?id={self.group_id}"
        self.browser.visit(url)
        
        # Debug: Print all text on the page to see what's available
        logger.info("Page loaded, checking for 'Group Picks' text...")
        all_elements_with_text = self.browser.find_by_xpath("//*[contains(text(), 'Group')]")
        logger.info(f"Found {len(all_elements_with_text)} elements containing 'Group':")
        for elem in all_elements_with_text[:10]:  # Show first 10
            logger.info(f"  Element text: '{elem.text}'")
        
        all_pick_elements = self.browser.find_by_xpath("//*[contains(text(), 'Pick')]")
        logger.info(f"Found {len(all_pick_elements)} elements containing 'Pick':")
        for elem in all_pick_elements[:10]:  # Show first 10
            logger.info(f"  Element text: '{elem.text}'")
        
        try:
            # Find the "Group Picks" button and wait for it to be present
            group_picks_button = self.browser.find_by_text("Group Picks", wait_time=10).first

            # Use a direct JavaScript click which is more robust against interception
            self.browser.execute_script("arguments[0].click();", group_picks_button._element)
        except Exception as e:
            screenshot_path = "error_navigate_to_group_picks.png"
            logger.info("Taking full-page screenshot...")
            screenshot_b64 = self.browser.driver.execute_cdp_cmd(
                "Page.captureScreenshot",
                {"format": "png", "captureBeyondViewport": True},
            )["data"]
            with open(screenshot_path, "wb") as f:
                f.write(base64.b64decode(screenshot_b64))
            logger.error(
                f"Failed to click 'Group Picks'. Full-page screenshot saved to {screenshot_path}"
            )
            raise e

    def _scrape_all_weeks(self, week=None):
        """
        Scrapes the pick data for all available weeks.
        If a week is provided, only that week will be scraped.
        Uses parallel processing for better performance.
        Handles both cases: with dropdown (multiple weeks) and without (first week only).
        """
        # First, check if there's a week dropdown
        week_options = self._get_week_options()
        weeks_to_soups = {w: [] for w in range(19)}
        
        if not week_options:
            # No dropdown found - this is likely the first week scenario
            logger.info("No week dropdown found. Scraping current page as week 1.")
            
            # Check if there's actually a pick grid on the current page
            try:
                self.wait.until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//*[contains(@class, 'GroupPickGrid-table')]")
                    )
                )
                logger.info("GroupPickGrid table found on current page")
            except TimeoutException:
                logger.error("No GroupPickGrid table found on current page")
                return weeks_to_soups
            
            # If a specific week was requested and it's not week 1, return empty
            if week is not None and week != 1:
                logger.info(f"Week {week} was requested but only week 1 is available.")
                return weeks_to_soups
            
            # Scrape the current page as week 1
            try:
                pick_grids = self._scrape_pages_for_week(1)
                soups = []
                for pick_grid in pick_grids:
                    soups.append(BeautifulSoup(pick_grid, "html.parser"))
                weeks_to_soups[1] = soups
                logger.info(f"Successfully scraped week 1 with {len(soups)} page(s)")
            except Exception as e:
                logger.error(f"Failed to scrape week 1: {e}")
            
            return weeks_to_soups
        
        # Dropdown found - process normally
        available_weeks = []
        
        for week_option in week_options:
            week_num_text = week_option.text
            try:
                week_num = int(week_num_text.lower().split("week ")[-1])
                if week is None or week_num == week:
                    available_weeks.append((week_num, week_option.value))
            except (ValueError, IndexError):
                logger.error(f"Could not parse week number from: {week_num_text}")
                continue
        
        logger.info(f"Found {len(available_weeks)} weeks to scrape: {[w[0] for w in available_weeks]}")
        
        # Use parallel processing to scrape weeks
        max_workers = min(4, len(available_weeks))  # Limit concurrent browsers
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all week scraping tasks
            future_to_week = {
                executor.submit(self._scrape_single_week_parallel, week_num, week_value): week_num
                for week_num, week_value in available_weeks
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_week):
                week_num = future_to_week[future]
                try:
                    week_soups = future.result()
                    weeks_to_soups[week_num] = week_soups
                    logger.info(f"Completed scraping week {week_num}")
                except Exception as e:
                    logger.error(f"Failed to scrape week {week_num}: {e}")
        
        return weeks_to_soups

    def _scrape_single_week_parallel(self, week_num, week_value):
        """
        Scrapes a single week using its own browser instance.
        This method is designed to be run in parallel.
        """
        logger.info(f"Starting parallel scrape for week {week_num}")
        
        try:
            with Browser("chrome", headless=True) as browser:  # Use headless for parallel execution
                wait = WebDriverWait(browser.driver, 20)
                
                # Navigate to the group picks page
                url = f"https://fantasy.espn.com/games/nfl-pigskin-pickem-2025/group?id={self.group_id}"
                browser.visit(url)
                
                # Click Group Picks button
                try:
                    group_picks_button = browser.find_by_text("Group Picks", wait_time=10).first
                    browser.execute_script("arguments[0].click();", group_picks_button._element)
                except Exception as e:
                    logger.error(f"Failed to click 'Group Picks' for week {week_num}: {e}")
                    return []
                
                # Wait for dropdown and select the specific week (if dropdown exists)
                try:
                    # Use shorter timeout to check for dropdown
                    short_wait = WebDriverWait(browser.driver, 5)
                    short_wait.until(
                        EC.presence_of_all_elements_located(
                            (By.XPATH, "//*[contains(@class, 'dropdown__select')]")
                        )
                    )
                    weeks_dropdown = browser.find_by_xpath(
                        "//*[contains(@class, 'dropdown__select')]"
                    )
                    weeks_dropdown.select(week_value)
                    logger.info(f"Selected week {week_num} from dropdown")
                    
                    # Wait for table to reload
                    wait.until(
                        EC.presence_of_element_located(
                            (By.XPATH, "//*[contains(@class, 'GroupPickGrid-table')]")
                        )
                    )
                except TimeoutException:
                    # No dropdown found - this is expected for first week
                    logger.info(f"No dropdown found for week {week_num} - using current page")
                    # Just wait for the table to be present
                    try:
                        wait.until(
                            EC.presence_of_element_located(
                                (By.XPATH, "//*[contains(@class, 'GroupPickGrid-table')]")
                            )
                        )
                    except TimeoutException:
                        logger.error(f"No GroupPickGrid table found for week {week_num}")
                        return []
                except Exception as e:
                    logger.error(f"Failed to select week {week_num}: {e}")
                    return []
                
                # Scrape all pages for this week
                pick_grids = self._scrape_pages_for_week_parallel(week_num, browser, wait)
                
                # Convert to BeautifulSoup objects
                soups = []
                for pick_grid in pick_grids:
                    soups.append(BeautifulSoup(pick_grid, "html.parser"))
                
                logger.info(f"Successfully scraped week {week_num} with {len(soups)} page(s)")
                return soups
                
        except Exception as e:
            logger.error(f"Error scraping week {week_num}: {e}")
            return []

    def _get_week_options(self):
        """
        Waits for and returns the week dropdown options.
        Returns empty list if no dropdown is found (e.g., first week of season).
        """
        try:
            # Use a shorter timeout and don't log as error if not found
            short_wait = WebDriverWait(self.browser.driver, 5)  # Shorter timeout
            short_wait.until(
                EC.presence_of_all_elements_located(
                    (By.XPATH, "//*[contains(@class, 'dropdown__select')]")
                )
            )
            weeks_dropdown = self.browser.find_by_xpath(
                "//*[contains(@class, 'dropdown__select')]"
            )
            options = weeks_dropdown.find_by_tag("option")
            logger.info(f"Found week dropdown with {len(options)} options")
            return options
        except TimeoutException:
            logger.info("No weeks dropdown found - likely first week of season")
            return []
        except Exception as e:
            logger.warning(f"Error looking for weeks dropdown: {e}")
            return []

    def _select_week(self, week_option):
        """
        Selects a week from the dropdown and returns its number.
        """
        week_num_text = week_option.text
        try:
            week_num = int(week_num_text.lower().split("week ")[-1])
            weeks_dropdown = self.browser.find_by_xpath(
                "//*[contains(@class, 'dropdown__select')]"
            )
            weeks_dropdown.select(week_option.value)
            # Wait for table to reload
            self.wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//*[contains(@class, 'GroupPickGrid-table')]")
                )
            )
            return week_num, weeks_dropdown
        except (ValueError, IndexError):
            logger.error(f"Could not parse week number from: {week_num_text}")
            return None, None

    def _scrape_pages_for_week(self, week_num):
        """
        Scrapes all pages for a given week.
        """
        pick_grids = []
        logger.info(f"Starting pagination for Week {week_num}")
        self._go_to_first_page()

        page_num = 1
        while True:
            logger.info(f"Processing Week {week_num}, Page {page_num}")
            pick_grid_html = self._get_pick_grid_html(week_num, page_num)
            if pick_grid_html:
                pick_grids.append(pick_grid_html)
                logger.info(f"Successfully captured HTML for Week {week_num}, Page {page_num}")
            else:
                logger.warning(f"No HTML captured for Week {week_num}, Page {page_num}")

            # DEBUG: Before trying to go to next page, let's see the current pagination state
            logger.info(f"Attempting to navigate to next page from page {page_num}")
            if not self._go_to_next_page():
                logger.info(f"No more pages available for Week {week_num}. Total pages processed: {page_num}")
                break
            page_num += 1
            
            # DEBUG: Safety check to prevent infinite loops
            if page_num > 50:  # Reasonable upper limit
                logger.warning(f"Reached page limit of 50 for Week {week_num}, stopping pagination")
                break

        logger.info(f"Completed pagination for Week {week_num}. Total grids collected: {len(pick_grids)}")
        return pick_grids

    def _scrape_pages_for_week_parallel(self, week_num, browser, wait):
        """
        Scrapes all pages for a given week using the provided browser instance.
        This is the parallel version of _scrape_pages_for_week.
        """
        pick_grids = []
        logger.info(f"Starting pagination for Week {week_num} (parallel)")
        self._go_to_first_page_parallel(browser)

        page_num = 1
        while True:
            logger.info(f"Processing Week {week_num}, Page {page_num} (parallel)")
            pick_grid_html = self._get_pick_grid_html_parallel(week_num, page_num, browser, wait)
            if pick_grid_html:
                pick_grids.append(pick_grid_html)
                logger.info(f"Successfully captured HTML for Week {week_num}, Page {page_num} (parallel)")
            else:
                logger.warning(f"No HTML captured for Week {week_num}, Page {page_num} (parallel)")

            logger.info(f"Attempting to navigate to next page from page {page_num} (parallel)")
            if not self._go_to_next_page_parallel(browser):
                logger.info(f"No more pages available for Week {week_num}. Total pages processed: {page_num} (parallel)")
                break
            page_num += 1
            
            if page_num > 50:  # Safety check
                logger.warning(f"Reached page limit of 50 for Week {week_num}, stopping pagination (parallel)")
                break

        logger.info(f"Completed pagination for Week {week_num}. Total grids collected: {len(pick_grids)} (parallel)")
        return pick_grids

    def _get_pick_grid_html(self, week_num, page_num):
        """
        Waits for the pick grid to be present and returns its HTML.
        """
        try:
            pick_grid_xpath = "//*[contains(@class, 'GroupPickGrid-table')]"
            self.wait.until(EC.presence_of_element_located((By.XPATH, pick_grid_xpath)))
            pick_grid = self.browser.find_by_xpath(pick_grid_xpath).first
            self.browser.execute_script(
                "arguments[0].scrollIntoView(true);", pick_grid._element
            )
            self.wait.until(EC.visibility_of(pick_grid._element))
            return pick_grid["outerHTML"]
        except (TimeoutException, ElementDoesNotExist):
            logger.error(f"No pick grid found for Week {week_num}, Page {page_num}")
            return None

    def _get_pick_grid_html_parallel(self, week_num, page_num, browser, wait):
        """
        Parallel version of _get_pick_grid_html.
        """
        try:
            pick_grid_xpath = "//*[contains(@class, 'GroupPickGrid-table')]"
            wait.until(EC.presence_of_element_located((By.XPATH, pick_grid_xpath)))
            pick_grid = browser.find_by_xpath(pick_grid_xpath).first
            browser.execute_script(
                "arguments[0].scrollIntoView(true);", pick_grid._element
            )
            wait.until(EC.visibility_of(pick_grid._element))
            return pick_grid["outerHTML"]
        except (TimeoutException, ElementDoesNotExist):
            logger.error(f"No pick grid found for Week {week_num}, Page {page_num} (parallel)")
            return None

    def _go_to_first_page(self):
        """
        Navigates to the first page of picks for a week.
        """
        logger.info("Navigating to first page...")
        prev_clicks = 0
        while self._click_pagination_button("prev"):
            prev_clicks += 1
            logger.info(f"Clicked 'prev' button {prev_clicks} times")
            # Safety check to prevent infinite loops
            if prev_clicks > 20:
                logger.warning("Clicked 'prev' button too many times, stopping")
                break
        logger.info(f"Reached first page after {prev_clicks} 'prev' clicks")

    def _go_to_first_page_parallel(self, browser):
        """
        Parallel version of _go_to_first_page.
        """
        logger.info("Navigating to first page (parallel)...")
        prev_clicks = 0
        while self._click_pagination_button_parallel("prev", browser):
            prev_clicks += 1
            logger.info(f"Clicked 'prev' button {prev_clicks} times (parallel)")
            if prev_clicks > 20:
                logger.warning("Clicked 'prev' button too many times, stopping (parallel)")
                break
        logger.info(f"Reached first page after {prev_clicks} 'prev' clicks (parallel)")

    def _go_to_next_page(self):
        """
        Navigates to the next page of picks, if available. Returns False if no next page.
        """
        return self._click_pagination_button("next")

    def _go_to_next_page_parallel(self, browser):
        """
        Parallel version of _go_to_next_page.
        """
        return self._click_pagination_button_parallel("next", browser)

    def _click_pagination_button(self, direction):
        """
        Clicks the 'next' or 'prev' pagination button.
        """
        # Try multiple XPath patterns since ESPN may have changed their CSS
        xpaths_to_try = [
            # Original pattern
            f"//button[contains(@class, 'Pagination__Button--{direction}') and not(@disabled)]",
            # More generic patterns
            f"//button[contains(@class, '{direction}') and not(@disabled)]",
            f"//button[contains(@class, 'pagination') and contains(@class, '{direction}') and not(@disabled)]",
            # Even more generic - look for buttons with direction in text or aria-label
            f"//button[contains(text(), '{direction}') and not(@disabled)]",
            f"//button[contains(@aria-label, '{direction}') and not(@disabled)]"
        ]
        
        logger.info(f"Looking for {direction} pagination button...")
        
        # DEBUG: Check what pagination buttons exist
        all_buttons = self.browser.find_by_xpath("//button")
        pagination_candidates = []
        for btn in all_buttons:
            try:
                # Look for buttons that might be pagination
                btn_html = btn['outerHTML'] if 'outerHTML' in btn else str(btn._element)
                if any(keyword in btn_html.lower() for keyword in ['pagination', 'next', 'prev', 'page']):
                    pagination_candidates.append(btn_html[:200])  # First 200 chars
            except:
                pass
        
        logger.info(f"Found {len(pagination_candidates)} potential pagination buttons")
        for i, candidate in enumerate(pagination_candidates[:3]):  # Show first 3
            logger.info(f"  Candidate {i+1}: {candidate}")
        
        # Try each XPath pattern
        for i, xpath in enumerate(xpaths_to_try):
            try:
                logger.info(f"Trying XPath pattern {i+1}: {xpath}")
                buttons = self.browser.find_by_xpath(xpath)
                
                if buttons:
                    button = buttons.first
                    logger.info(f"Found {direction} button with pattern {i+1}")
                    
                    old_button_element = button._element
                    self.browser.execute_script(
                        "arguments[0].scrollIntoView(true);", old_button_element
                    )
                    
                    # Use JavaScript to click the button
                    self.browser.execute_script("arguments[0].click();", old_button_element)
                    logger.info(f"Clicked {direction} button, waiting for page refresh...")
                    
                    # Wait for the old button element to become stale, or for content to change
                    try:
                        # First, wait a moment for the click to register
                        import time
                        time.sleep(1)
                        
                        # Try waiting for staleness, but with a shorter timeout
                        try:
                            WebDriverWait(self.browser.driver, 5).until(EC.staleness_of(old_button_element))
                            logger.info(f"Page refreshed after clicking {direction} button (staleness detected)")
                            return True
                        except TimeoutException:
                            # If staleness doesn't work, check if the button state changed
                            try:
                                current_buttons = self.browser.find_by_xpath(xpath)
                                if not current_buttons:
                                    logger.info(f"Page refreshed after clicking {direction} button (button disappeared)")
                                    return True
                                
                                # Check if button became disabled
                                new_button = current_buttons.first
                                if 'disabled' in new_button['class'] or new_button.get('disabled'):
                                    logger.info(f"Page refreshed after clicking {direction} button (button became disabled)")
                                    return True
                                    
                            except:
                                pass
                            
                            logger.warning(f"Page might not have refreshed after clicking {direction} button, but continuing...")
                            return True  # Continue anyway since we clicked the button
                            
                    except Exception as e:
                        logger.warning(f"Error checking page refresh after clicking {direction} button: {e}")
                        return True  # Continue anyway since we clicked the button
                        
            except (ElementDoesNotExist, TimeoutException):
                logger.info(f"Pattern {i+1} didn't find any {direction} buttons")
                continue
            except Exception as e:
                logger.warning(f"Error with pattern {i+1}: {e}")
                continue
        
        # If we get here, no pattern worked
        logger.info(f"No {direction} button found with any pattern - likely at first/last page")
        
        # Take screenshot for debugging
        screenshot_path = f"debug_no_{direction}_button.png"
        try:
            screenshot_b64 = self.browser.driver.execute_cdp_cmd(
                "Page.captureScreenshot",
                {"format": "png", "captureBeyondViewport": True},
            )["data"]
            with open(screenshot_path, "wb") as f:
                f.write(base64.b64decode(screenshot_b64))
            logger.info(f"Debug screenshot saved to {screenshot_path}")
        except Exception as screenshot_error:
            logger.error(f"Could not take debug screenshot: {screenshot_error}")
        
        return False

    def _click_pagination_button_parallel(self, direction, browser):
        """
        Parallel version of _click_pagination_button.
        """
        xpaths_to_try = [
            f"//button[contains(@class, 'Pagination__Button--{direction}') and not(@disabled)]",
            f"//button[contains(@class, '{direction}') and not(@disabled)]",
            f"//button[contains(@class, 'pagination') and contains(@class, '{direction}') and not(@disabled)]",
            f"//button[contains(text(), '{direction}') and not(@disabled)]",
            f"//button[contains(@aria-label, '{direction}') and not(@disabled)]"
        ]
        
        logger.info(f"Looking for {direction} pagination button (parallel)...")
        
        for i, xpath in enumerate(xpaths_to_try):
            try:
                logger.info(f"Trying XPath pattern {i+1} (parallel): {xpath}")
                buttons = browser.find_by_xpath(xpath)
                
                if buttons:
                    button = buttons.first
                    logger.info(f"Found {direction} button with pattern {i+1} (parallel)")
                    
                    old_button_element = button._element
                    browser.execute_script(
                        "arguments[0].scrollIntoView(true);", old_button_element
                    )
                    
                    browser.execute_script("arguments[0].click();", old_button_element)
                    logger.info(f"Clicked {direction} button, waiting for page refresh (parallel)...")
                    
                    try:
                        import time
                        time.sleep(1)
                        
                        try:
                            WebDriverWait(browser.driver, 5).until(EC.staleness_of(old_button_element))
                            logger.info(f"Page refreshed after clicking {direction} button (parallel)")
                            return True
                        except TimeoutException:
                            try:
                                current_buttons = browser.find_by_xpath(xpath)
                                if not current_buttons:
                                    logger.info(f"Page refreshed after clicking {direction} button - button disappeared (parallel)")
                                    return True
                                
                                new_button = current_buttons.first
                                if 'disabled' in new_button['class'] or new_button.get('disabled'):
                                    logger.info(f"Page refreshed after clicking {direction} button - button disabled (parallel)")
                                    return True
                                    
                            except:
                                pass
                            
                            logger.warning(f"Page might not have refreshed after clicking {direction} button, continuing (parallel)...")
                            return True
                            
                    except Exception as e:
                        logger.warning(f"Error checking page refresh after clicking {direction} button (parallel): {e}")
                        return True
                        
            except (ElementDoesNotExist, TimeoutException):
                logger.info(f"Pattern {i+1} didn't find any {direction} buttons (parallel)")
                continue
            except Exception as e:
                logger.warning(f"Error with pattern {i+1} (parallel): {e}")
                continue
        
        logger.info(f"No {direction} button found with any pattern - likely at first/last page (parallel)")
        return False

    def _parse_soups(self, weeks_to_soups):
        """
        Parses the collected BeautifulSoup objects to populate team picks.
        """
        for week, soups in weeks_to_soups.items():
            if not soups:
                continue
            for soup in soups:
                tables = soup.find_all("table")
                idx_to_name = self._parse_team_names(tables)
                self._parse_picks(tables, idx_to_name, week)

    def _parse_team_names(self, tables):
        """
        Parses team names and owners from the tables.
        """
        idx_to_name = {}
        for table in tables:
            if "GROUP ENTRIES" in table.text.upper():
                rows = table.find_all("tr")
                for row in rows[2:]:  # Skip header rows
                    idx = int(row["data-idx"])
                    name_cell = row.find(
                        "td", {"class": lambda x: x and "GroupPickGrid-column--entryName" in x}
                    )
                    if name_cell:
                        name_anchor = name_cell.find("a", {"class": "GroupPickGrid-entryLink"})
                        if name_anchor:
                            name = name_anchor.text.strip()
                            idx_to_name[idx] = name
                            # Thread-safe access to self.teams
                            with self.teams_lock:
                                if name not in self.teams:
                                    self.teams[name] = Team(name, "owner")
        return idx_to_name

    def _parse_picks(self, tables, idx_to_name, week):
        """
        Parses the picks for each team.
        """
        logger.info(f"Parsing picks for week {week}")
        logger.info(f"Have {len(idx_to_name)} teams in idx_to_name mapping")
        
        for table_idx, table in enumerate(tables):
            if "PICKS" in table.text.upper():
                logger.info(f"Found picks table {table_idx}")
                rows = table.find_all("tr")
                logger.info(f"Table has {len(rows)} rows")
                
                for row_idx, row in enumerate(rows):
                    if "data-idx" not in row.attrs:
                        continue
                        
                    team_idx = int(row["data-idx"])
                    team_name = idx_to_name.get(team_idx)
                    logger.info(f"Row {row_idx}: team_idx={team_idx}, team_name={team_name}")
                    
                    # Thread-safe access to self.teams
                    with self.teams_lock:
                        if team_name and team_name in self.teams:
                            team = self.teams[team_name]
                            picks = row.find_all("td", {"class": lambda x: x and "GroupPickGrid-column--pick" in x})
                            logger.info(f"  Found {len(picks)} pick cells for {team_name}")
                            
                            picks_added = 0
                            for pick_idx, pick_cell in enumerate(picks):
                                pick_classes = pick_cell.get("class", [])
                                has_no_pick = "noPick" in pick_classes
                                has_link = pick_cell.find("a") is not None
                                has_image = pick_cell.find("img") is not None
                                logger.info(f"    Pick {pick_idx}: classes={pick_classes}, has_no_pick={has_no_pick}, has_link={has_link}, has_image={has_image}")
                                
                                # Add pick if it's not a "noPick" and has either a link or an image (team logo)
                                if not has_no_pick and (has_link or has_image):
                                    team.add_weekly_pick(week, Pick(pick_cell))
                                    picks_added += 1
                                    
                            logger.info(f"  Added {picks_added} picks for {team_name}")
                        else:
                            if team_name:
                                logger.warning(f"Team {team_name} not found in self.teams")

    def get_teams(self):
        return list(self.teams.values())