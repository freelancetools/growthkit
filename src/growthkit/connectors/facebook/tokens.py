#!/usr/bin/env python3
"""
Facebook Graph API Token Generator

This script exchanges short-lived user access tokens for long-lived tokens
and retrieves page access tokens. It uses config.ini for configuration management
and provides both CLI and interactive modes.

By default, tokens are saved to timestamped JSON files in the tokens/ directory.
Use --no-save to skip saving tokens.

Usage:
    python tokens.py --user-token <token> [--page-id <id>]
    python tokens.py --config <config_file> [--no-save]
"""

import sys
import json
import time
import argparse
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from growthkit.utils.style import ansi
from growthkit.utils.logs import report
from growthkit.connectors.facebook import engine
from growthkit.connectors.facebook.engine import TokenManager
from growthkit.connectors.facebook.schema import Token, Page

logger = report.settings(__file__)
config = engine.load(Path("config", "facebook", "facebook.ini"))


def make_api_request(url: str) -> Dict[str, Any]:
    """Make a request to Facebook Graph API"""
    logger.info("Making API request to: %s", url)
    print(f"Making API request to: {ansi.cyan}{url[:100]}"
          f"{'...' if len(url) > 100 else ''}{ansi.reset}")

    try:
        with urllib.request.urlopen(url) as response:
            logger.info("API request successful, status: %s", response.status)
            print(f"API request {ansi.green}successful{ansi.reset}, "
                  f"status: {ansi.green}{response.status}{ansi.reset}")

            response_text = response.read().decode()
            logger.debug("Raw API response: %s", response_text)
            print(f"Raw API response: {ansi.grey}{response_text[:200]}"
                  f"{'...' if len(response_text) > 200 else ''}{ansi.reset}")

            data = json.loads(response_text)
            logger.info("API response parsed successfully")
            return data

    except urllib.error.HTTPError as e:
        logger.error("HTTP Error %s: %s", e.code, e.reason)
        print(f"HTTP {ansi.red}Error{ansi.reset} {e.code}: {e.reason}")

        try:
            error_text = e.read().decode()
            error_data = json.loads(error_text)
            logger.error("API Error details: %s", error_data)
            print(f"API Error details: {ansi.red}{error_data}{ansi.reset}")
        except json.JSONDecodeError as parse_error:
            logger.error("Could not parse error response: %s", parse_error)
            print(f"{ansi.red}Could not parse error response: {parse_error}{ansi.reset}")
        raise

    except (urllib.error.URLError, OSError) as e:
        logger.error("Request failed with exception: %s", str(e))
        print(f"Request {ansi.red}failed{ansi.reset}: {ansi.red}{str(e)}{ansi.reset}")
        raise


def get_long_lived_user_token(short_lived_token: str) -> Token:
    """Exchange short-lived user token for long-lived token"""
    logger.info("Exchanging short-lived token for long-lived token")
    print(f"Exchanging {ansi.yellow}short-lived token{ansi.reset} for "
          f"{ansi.green}long-lived token{ansi.reset}")

    # Log the parameters being used (with sensitive data masked)
    logger.info("Token exchange parameters - grant_type: fb_exchange_token, "
                "client_id: %s, client_secret: %s..., token: %s...",
                config.app.app_id,
                config.app.app_secret[:8] if config.app.app_secret else 'None',
                short_lived_token[:20] if short_lived_token else 'None')

    print("Token exchange parameters:")
    print(f"  Grant Type: {ansi.yellow}fb_exchange_token{ansi.reset}")
    print(f"  Client ID: {ansi.yellow}{config.app.app_id}{ansi.reset}")
    client_secret_display = (
        f"{config.app.app_secret[:8]}"
        f"{'...' if config.app.app_secret and len(config.app.app_secret) > 8 else ''}"
        if config.app.app_secret else 'None'
    )
    print(f"  Client Secret: {ansi.yellow}{client_secret_display}{ansi.reset}")
    token_display = (
        f"{short_lived_token[:20]}"
        f"{'...' if short_lived_token and len(short_lived_token) > 20 else ''}"
        if short_lived_token else 'None'
    )
    print(f"  Token: {ansi.yellow}{token_display}{ansi.reset}")
    print(f"  API Base URL: {ansi.cyan}{config.app.base_url}{ansi.reset}")

    params = {
        'grant_type': 'fb_exchange_token',
        'client_id': config.app.app_id,
        'client_secret': config.app.app_secret,
        'fb_exchange_token': short_lived_token
    }

    url = f"{config.app.base_url}/oauth/access_token?{urllib.parse.urlencode(params)}"

    logger.info("Requesting long-lived user access token...")
    print("Requesting long-lived user access token...")
    data = make_api_request(url)

    expires_at = None
    if 'expires_in' in data:
        expires_at = int(time.time() + data['expires_in'])

    return Token(
        access_token=data['access_token'],
        expires_in=data.get('expires_in'),
        expires_at=expires_at,
        token_type=data.get('token_type', 'bearer')
    )


def get_all_paginated_data(url: str, user_token: str) -> list:
    """Get all data from a paginated Facebook API endpoint"""
    all_data = []
    current_url = url
    page_count = 0

    print(f"\n{ansi.cyan}PAGINATION DEBUG: Starting data collection from {url}{ansi.reset}")

    while current_url:
        page_count += 1
        try:
            # Make the request
            if '?' in current_url:
                current_url += f"&access_token={user_token}"
            else:
                current_url += f"?access_token={user_token}"

            print(f"  Page {page_count}: Requesting {len(all_data)} items so far...")
            response_data = make_api_request(current_url)

            # Add this batch of data
            data_batch = response_data.get('data', [])
            all_data.extend(data_batch)

            print(f"  Page {page_count}: Got {len(data_batch)} items (total: {len(all_data)})")

            # Check for next page
            paging = response_data.get('paging', {})
            next_url = paging.get('next')

            if next_url:
                print(f"  Page {page_count}: Next page available")
                # Remove access_token from next URL since we'll add it again
                if 'access_token=' in next_url:
                    # Parse the URL and rebuild without access_token
                    parsed = urllib.parse.urlparse(next_url)
                    query_params = dict(urllib.parse.parse_qsl(parsed.query))
                    query_params.pop('access_token', None)
                    query_string = urllib.parse.urlencode(query_params)
                    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    current_url = f"{base_url}?{query_string}" if query_string else base_url
                else:
                    current_url = next_url
            else:
                print(f"  Page {page_count}: No more pages available")
                current_url = None

            # Safety check to prevent infinite loops
            if page_count > 50:  # Reasonable safety limit
                warning_msg = "WARNING: Reached safety limit of 50 pages. Stopping pagination."
                print(f"  {ansi.yellow}{warning_msg}{ansi.reset}")
                break

        except (urllib.error.HTTPError, urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            logger.error("Pagination request failed: %s", str(e))
            print(f"  Page {page_count}: {ansi.red}Request failed: {str(e)}{ansi.reset}")
            break

    pagination_msg = f"PAGINATION COMPLETE: {len(all_data)} total items across {page_count} pages"
    print(f"{ansi.cyan}{pagination_msg}{ansi.reset}")
    return all_data


def get_business_manager_pages(user_token: str) -> tuple[Dict[str, Page], list]:
    """Get pages accessible through Business Manager"""
    print(f"\n{ansi.cyan}DEBUG: Checking Business Manager accounts...{ansi.reset}")

    # Get Business Manager accounts the user has access to (with pagination)
    businesses_url = f"{config.app.base_url}/me/businesses"
    businesses = get_all_paginated_data(businesses_url, user_token)

    print(f"Found {len(businesses)} Business Manager account(s):")
    for i, business in enumerate(businesses, 1):
        business_id = business['id']
        business_name = business.get('name', 'Unknown')
        name_id_display = f"{business_name} (ID: {business_id})"
        print(f"  {i}. {ansi.yellow}{name_id_display}{ansi.reset}")

    if not businesses:
        print("No Business Manager accounts found.")
        return {}, []

    # Get pages from each Business Manager
    all_business_pages = {}
    business_info = []
    target_pages_found = []

    for business in businesses:
        business_id = business['id']
        business_name = business.get('name', 'Unknown')

        print(f"\n{ansi.cyan}Getting pages from Business Manager: {business_name}{ansi.reset}")

        # Get pages owned by this business (with pagination)
        business_pages_url = f"{config.app.base_url}/{business_id}/owned_pages"
        try:
            pages = get_all_paginated_data(business_pages_url, user_token)

            # Count pages and look for target pages first
            target_pages_in_business = []
            for page in pages:
                page_name = page.get('name', 'Unknown')
                if False:  # remove client-specific targeting
                    target_pages_in_business.append((page['id'], page_name))

            print(f"Found {len(pages)} page(s) in {business_name}")
            if target_pages_in_business:
                print(f"{ansi.magenta}🎯 TARGET PAGES FOUND:{ansi.reset}")
                for page_id, page_name in target_pages_in_business:
                    page_display = f"→ {page_name} (ID: {page_id})"
                    print(f"  {ansi.magenta}{page_display}{ansi.reset}")
                    target_pages_found.append((page_name, page_id, business_name))

            # Process pages quietly, only show token success/failure summary
            successful_tokens = 0
            failed_tokens = 0

            for page in pages:
                page_id = page['id']
                page_name = page.get('name', 'Unknown')
                category = page.get('category', 'Unknown')

                # Try to get page access token quietly
                page_token_url = (
                    f"{config.app.base_url}/{page_id}"
                    f"?fields=access_token&access_token={user_token}"
                )
                try:
                    page_token_data = make_api_request(page_token_url)
                    if 'access_token' in page_token_data:
                        page_config = Page(
                            page_id=page_id,
                            page_name=page_name,
                            category=category,
                            page_access_token=Token(
                                access_token=page_token_data['access_token'],
                                expires_at=None
                            )
                        )
                        all_business_pages[page_id] = page_config
                        successful_tokens += 1

                        # Only show details for target pages
                        if any(target_id == page_id for target_id, _ in target_pages_in_business):
                            print(f"  {ansi.green}✓ {page_name} - TOKEN RETRIEVED{ansi.reset}")
                    else:
                        failed_tokens += 1
                except (urllib.error.HTTPError, urllib.error.URLError, OSError,
                        json.JSONDecodeError, KeyError):
                    failed_tokens += 1
                    # Only show failures for target pages
                    is_target_page = any(target_id == page_id 
                                       for target_id, _ in target_pages_in_business)
                    if is_target_page:
                        error_msg = ("✗ {page_name} - Token failed "
                                   "(needs pages_read_engagement permission)").format(page_name=page_name)
                        print(f"  {ansi.red}{error_msg}{ansi.reset}")

            # Show summary
            success_msg = f"{successful_tokens} successful"
            failed_msg = f"{failed_tokens} failed"
            print(f"  Tokens: {ansi.green}{success_msg}{ansi.reset}, "
                  f"{ansi.red}{failed_msg}{ansi.reset}")

            business_info.append({
                'business_id': business_id,
                'business_name': business_name,
                'page_count': len(pages),
                'successful_tokens': successful_tokens,
                'failed_tokens': failed_tokens
            })

        except (urllib.error.HTTPError, urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            print(f"Failed to get pages from {business_name}: {ansi.red}{str(e)}{ansi.reset}")

    # Show target pages summary
    if target_pages_found:
        print(f"\n{ansi.magenta}🎯 TARGET PAGES SUMMARY:{ansi.reset}")
        for page_name, page_id, business_name in target_pages_found:
            status = "✓ Token Available" if page_id in all_business_pages else "✗ Token Failed"
            color = ansi.green if page_id in all_business_pages else ansi.red
            print(f"  • {ansi.yellow}{page_name}{ansi.reset} ({page_id})")
            print(f"    Business: {business_name}")
            print(f"    Status: {color}{status}{ansi.reset}")

    return all_business_pages, business_info


def get_page_access_tokens(
        user_token: str,
        target_page_id: Optional[str] = None
) -> tuple[Dict[str, Page], dict]:
    """Get page access tokens for all pages or a specific page"""
    logger.info("Getting page access tokens")
    print(f"Getting {ansi.magenta}page access tokens{ansi.reset}...")

    # First get user ID - we need this for the accounts endpoint
    logger.info("Getting user ID via /me endpoint")
    print(f"Getting {ansi.cyan}user ID{ansi.reset} via /me endpoint...")

    user_url = f"{config.app.base_url}/me?access_token={user_token}"
    try:
        user_data = make_api_request(user_url)
        user_id = user_data['id']
        user_name = user_data.get('name', 'Unknown')
        logger.info("User info retrieved - ID: %s, Name: %s", user_id, user_name)
        print("User info retrieved:")
        print(f"  ID: {ansi.yellow}{user_id}{ansi.reset}")
        print(f"  Name: {ansi.yellow}{user_name}{ansi.reset}")
    except Exception as e:
        logger.error("Failed to get user ID: %s", str(e))
        print(f"{ansi.red}Failed to get user ID{ansi.reset}: {str(e)}")
        print(f"\n{ansi.yellow}Possible solutions:{ansi.reset}")
        print(f"  1. Go to {ansi.cyan}Facebook Graph API Explorer{ansi.reset}")
        print(f"  2. Select your app: {ansi.cyan}Page Content Toolkit{ansi.reset}")
        print(f"  3. Click {ansi.cyan}Add permissions{ansi.reset} and add:")
        print(f"     - {ansi.cyan}email{ansi.reset}")
        print(f"     - {ansi.cyan}public_profile{ansi.reset}")
        print(f"     - {ansi.cyan}pages_show_list{ansi.reset}")
        print(f"     - {ansi.cyan}pages_read_engagement{ansi.reset}")
        print(f"  4. Generate a new {ansi.cyan}User Access Token{ansi.reset}")
        print("  5. Run the script again with the new token")
        raise

    # Check token permissions/scope
    print(f"\n{ansi.cyan}DEBUG: Checking token permissions...{ansi.reset}")
    permissions_url = f"{config.app.base_url}/me/permissions?access_token={user_token}"
    try:
        permissions_data = make_api_request(permissions_url)
        print("Token permissions:")
        for perm in permissions_data.get('data', []):
            status = perm.get('status', 'unknown')
            permission = perm.get('permission', 'unknown')
            color = ansi.green if status == 'granted' else ansi.red
            print(f"  - {permission}: {color}{status}{ansi.reset}")

    except (urllib.error.HTTPError, urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        print(f"Could not retrieve permissions: {ansi.red}{str(e)}{ansi.reset}")

    # Get page access tokens from personal account (with pagination)
    pages_url = f"{config.app.base_url}/{user_id}/accounts"

    logger.info("Requesting page access tokens for user: %s", user_id)
    print(f"\nRequesting {ansi.magenta}personal page access tokens{ansi.reset} for "
          f"user: {ansi.yellow}{user_id}{ansi.reset}")

    # Get ALL personal pages with pagination
    personal_pages_data = get_all_paginated_data(pages_url, user_token)

    # Debug: Show summary instead of all pages
    print(f"Total personal pages found: {len(personal_pages_data)}")

    # Look for target pages in personal pages
    personal_target_pages = []
    for page_data in personal_pages_data:
        page_name = page_data.get('name', 'Unknown')
        # no client-specific targeting retained

    if personal_target_pages:
        print(f"{ansi.magenta}🎯 TARGET PAGES FOUND IN PERSONAL PAGES:{ansi.reset}")
        for page_id, page_name in personal_target_pages:
            personal_page_display = f"→ {page_name} (ID: {page_id})"
            print(f"  {ansi.magenta}{personal_page_display}{ansi.reset}")

    pages = {}
    logger.info("Processing %d pages from personal API response", len(personal_pages_data))

    # Process personal pages
    for page_data in personal_pages_data:
        page_id = page_data['id']
        page_name = page_data.get('name')

        # If target_page_id is specified, only process that page
        if target_page_id and page_id != target_page_id:
            logger.info("Skipping personal page: %s (%s) - not target page",
                       page_name, page_id)
            continue

        logger.info("Processing personal page: %s (%s)", page_name, page_id)
        page_config = Page(
            page_id=page_id,
            page_name=page_name,
            category=page_data.get('category'),
            page_access_token=Token(
                access_token=page_data['access_token'],
                expires_at=None
            )
        )
        pages[page_id] = page_config

    # Also check Business Manager pages
    business_pages, business_info = get_business_manager_pages(user_token)

    # Merge business pages with personal pages
    for page_id, business_page in business_pages.items():
        if target_page_id and page_id != target_page_id:
            logger.info("Skipping business page: %s (%s) - not target page",
                       business_page.page_name, page_id)
            continue
        pages[page_id] = business_page

    # Summary
    personal_count = len(personal_pages_data)
    total_count = len(pages)

    # Calculate Business Manager token stats
    total_bm_pages = sum(info.get('page_count', 0) for info in business_info)
    total_successful_tokens = sum(info.get('successful_tokens', 0) for info in business_info)

    print(f"\n{ansi.cyan}FINAL SUMMARY:{ansi.reset}")
    print(f"  Personal pages found: {ansi.yellow}{personal_count}{ansi.reset}")
    print(f"  Business Manager pages found: {ansi.yellow}{total_bm_pages}{ansi.reset}")
    print(f"  Total pages with tokens: {ansi.yellow}{total_count}{ansi.reset}")
    total_pages = total_bm_pages + personal_count
    success_rate = f"{total_successful_tokens} / {total_pages}"
    print(f"  Token success rate: {ansi.green}{success_rate}{ansi.reset}")

    if target_page_id:
        print(f"\n{ansi.cyan}TARGET PAGE CHECK:{ansi.reset}")
        print(f"  Looking for page ID: {ansi.yellow}{target_page_id}{ansi.reset}")
        if target_page_id in pages:
            target_page = pages[target_page_id]
            print(f"  {ansi.green}✓ Target page found: {target_page.page_name}{ansi.reset}")
        else:
            print(f"  {ansi.red}✗ Target page not found{ansi.reset}")
    else:
        print("  No specific target page - processing all available pages")

    user_info = {
        'user_id': user_id,
        'user_name': user_name,
        'business_accounts': business_info
    }

    return pages, user_info


def convert_expiration_time(expires_in: Optional[int]) -> Optional[datetime]:
    """Convert expires_in seconds to local datetime"""
    if expires_in is None:
        return None

    expiry_timestamp = time.time() + expires_in
    return datetime.fromtimestamp(expiry_timestamp, tz=timezone.utc).astimezone()


def display_expiration_info(token_info: Token, token_name: str) -> None:
    """Display token expiration information"""
    logger.info("Displaying token info for: %s", token_name)
    print(f"\n{ansi.cyan}{token_name}{ansi.reset} Token Information:")
    print(f"  Token: {ansi.yellow}{token_info.access_token[:20]}...{ansi.reset}")

    if token_info.expires_at:
        local_time = datetime.fromtimestamp(token_info.expires_at,
                                           tz=timezone.utc).astimezone()
        time_until = token_info.time_until_expiry()

        logger.info("Token expires at: %s", local_time.isoformat())
        print(f"  Expires: {ansi.yellow}{local_time.strftime('%Y-%m-%d %H:%M:%S %Z')}"
              f"{ansi.reset}")
        if time_until:
            days = time_until // 86400
            hours = (time_until % 86400) // 3600
            logger.info("Time until expiry: %d days, %d hours", days, hours)
            print(f"  Time until expiry: {ansi.green}{days}{ansi.reset} days, "
                  f"{ansi.green}{hours}{ansi.reset} hours")
        else:
            logger.warning("Token is expired")
            print(f"  Status: {ansi.red}EXPIRED{ansi.reset}")
    else:
        logger.info("Token does not expire")
        print(f"  Expires: {ansi.green}Never (or very long-lived){ansi.reset}")


def setup_argument_parser() -> argparse.ArgumentParser:
    """Set up and return the argument parser"""
    parser = argparse.ArgumentParser(description='Facebook Graph API Token Generator')
    parser.add_argument('-ai', '--app-id', help='App ID')
    parser.add_argument('-as', '--app-secret', help='App Secret')
    parser.add_argument('-t', '--temp-token', help='Short-lived user access token')
    parser.add_argument('-p', '--page-id', help='Specific page ID to get token for')
    return parser


def validate_token_input(args: argparse.Namespace) -> tuple[str, Optional[str]]:
    """Validate and return user token and page ID"""
    # Get token from CLI arg or config file
    temp_user_token = args.temp_token or config.token.access_token
    fb_page_id = args.page_id or config.page.page_id

    logger.info("Token source determination - CLI token: %s, Config token: %s",
                'provided' if args.temp_token else 'not provided',
                'available' if config.token.access_token else 'not available')

    if not fb_page_id:
        logger.info("No specific page ID specified, will process all pages")
        print(f"No specific {ansi.yellow}page ID{ansi.reset} specified, will process all pages")

    if not temp_user_token:
        logger.error("No user access token available")
        print(f"{ansi.red}Error:{ansi.reset} No user access token provided.")
        print("Please either:")
        print(f"  1. Use {ansi.cyan}--temp-token <token>{ansi.reset} argument")
        print(f"  2. Set {ansi.cyan}short_lived_token{ansi.reset} in the config file")
        print(f"  3. Get a token from {ansi.cyan}Facebook Graph API Explorer{ansi.reset}")
        sys.exit(1)

    logger.info("Using user token: %s... (length: %d)",
                temp_user_token[:20], len(temp_user_token))
    print(f"Using user token: {ansi.yellow}{temp_user_token[:20]}...{ansi.reset} "
          f"(length: {ansi.yellow}{len(temp_user_token)}{ansi.reset})")

    return temp_user_token, fb_page_id


def process_long_lived_token(temp_user_token: str, token_manager: TokenManager) -> Token:
    """Process step 1: Get long-lived user access token"""
    logger.info("Starting Step 1: Get long-lived user access token")
    print(f"\n{ansi.blue}Step 1:{ansi.reset} Getting long-lived user access token...")
    long_lived_user_token = get_long_lived_user_token(temp_user_token)

    # Update TokenManager with new token info
    token_manager.update_user_config(
        short_lived_token=temp_user_token,
        long_lived_token=long_lived_user_token
    )

    logger.info("Step 1 completed successfully")
    print(f"{ansi.green}Step 1 completed{ansi.reset}")
    display_expiration_info(long_lived_user_token, "Long-lived User")

    return long_lived_user_token


def process_page_tokens(long_lived_user_token: Token, fb_page_id: Optional[str],
                       token_manager: TokenManager) -> tuple[Dict[str, Page], dict]:
    """Process step 2: Get page access tokens"""
    logger.info("Starting Step 2: Get page access tokens")
    print(f"\n{ansi.blue}Step 2:{ansi.reset} Getting page access tokens...")
    pages, user_info = get_page_access_tokens(long_lived_user_token.access_token,
                                             fb_page_id)

    # Update TokenManager with retrieved user info
    token_manager.update_user_config(
        user_id=user_info['user_id'],
        user_name=user_info['user_name']
    )
    logger.info("Updated user config with ID: %s, Name: %s",
                user_info['user_id'], user_info['user_name'])

    if not pages:
        print("No pages found or no access to specified page.")
        return pages, user_info

    # Display page information and update TokenManager
    print(f"\n{ansi.magenta}Processing {len(pages)} page(s):{ansi.reset}")
    for page_id, page_cfg in pages.items():
        print(f"\nPage: {page_cfg.page_name} ({page_id})")
        print(f"  Category: {page_cfg.category}")
        display_expiration_info(page_cfg.page_access_token, "Page Access")

        # Add page to TokenManager
        token_manager.add_page_config(page_id, page_cfg)
        logger.info("Added page config for: %s", page_cfg.page_name)
        print(f"  → {ansi.green}Added to token manager{ansi.reset}")

    return pages, user_info


def save_and_display_results(token_manager: TokenManager) -> None:
    """Process step 3: Save tokens and display results"""
    logger.info("Starting Step 3: Save token data")
    print(f"\n{ansi.blue}Step 3:{ansi.reset} Saving token data...")
    saved_file = token_manager.save_run_data()
    logger.info("Token data saved to: %s", saved_file)
    print(f"Token data saved to: {ansi.cyan}{saved_file}{ansi.reset}")

    # Display summary
    summary = token_manager.get_summary()
    print(f"\n{ansi.magenta}Token Summary:{ansi.reset}")
    print(f"  Run ID: {ansi.yellow}{summary['run_id']}{ansi.reset}")
    print(f"  User: {ansi.yellow}{summary['user_name']}{ansi.reset} "
          f"({ansi.yellow}{summary['user_id']}{ansi.reset})")
    print(f"  Pages: {ansi.yellow}{summary['page_count']}{ansi.reset}")
    for page_name in summary['page_names']:
        print(f"    - {ansi.yellow}{page_name}{ansi.reset}")

    logger.info("Token generation completed successfully")
    print(f"\n✅ Token generation {ansi.green}completed successfully{ansi.reset}!")

    print("💡 Your tokens are now saved as timestamped JSON files.")
    print("📅 Tip: Add token expiration dates to your calendar for tracking.")


def main():
    """Main function - orchestrates the token generation workflow"""
    parser = setup_argument_parser()
    args = parser.parse_args()

    # Validate input and get tokens
    temp_user_token, fb_page_id = validate_token_input(args)

    # Initialize TokenManager
    token_manager = TokenManager()

    try:
        # Step 1: Get long-lived user token
        long_lived_user_token = process_long_lived_token(temp_user_token, token_manager)

        # Step 2: Get page access tokens
        process_page_tokens(long_lived_user_token, fb_page_id, token_manager)

        # Step 3: Save tokens and display results
        save_and_display_results(token_manager)

    except urllib.error.HTTPError as e:
        logger.error("HTTP error during token generation: %s", str(e))
        print(f"\n❌ HTTP {ansi.red}Error{ansi.reset}: {e}")
        sys.exit(1)

    except (urllib.error.URLError, OSError) as e:
        logger.error("Unexpected error during token generation: %s", str(e))
        print(f"\n❌ Unexpected {ansi.red}Error{ansi.reset}: {e}")
        print("Check the log file for detailed error information.")
        sys.exit(1)


if __name__ == '__main__':
    main()
