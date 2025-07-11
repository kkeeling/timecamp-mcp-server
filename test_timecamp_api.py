#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "httpx>=0.27.0",
# ]
# ///
"""
Direct API test for TimeCamp endpoints
Tests all the endpoints used by the MCP server to ensure they work correctly.

Usage:
    uv run test_timecamp_api.py YOUR_API_TOKEN
    
    Or set the TIMECAMP_API_TOKEN environment variable:
    TIMECAMP_API_TOKEN=your_token uv run test_timecamp_api.py
"""

import asyncio
import os
import sys
import json
import httpx
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# Configuration
BASE_URL = 'https://app.timecamp.com/third_party/api'

def xml_to_dict(element):
    """Convert XML element to dictionary (same as in the MCP server)"""
    result = {}
    
    # Handle empty XML response
    if len(element) == 0 and element.text is None:
        return result
        
    # If element has children, process them
    if len(element) > 0:
        # Check if all children have the same tag (list of items)
        child_tags = [child.tag for child in element]
        if len(set(child_tags)) == 1 and child_tags[0] == 'item':
            # This is a list of items
            items = []
            for child in element:
                item_dict = {}
                for subchild in child:
                    value = subchild.text
                    # Try to convert to appropriate type
                    if value is not None:
                        if value.isdigit():
                            value = int(value)
                        elif value.replace('.', '', 1).isdigit():
                            value = float(value)
                    item_dict[subchild.tag] = value
                items.append(item_dict)
            return items
        else:
            # This is a single object with various fields
            for child in element:
                if len(child) > 0:
                    result[child.tag] = xml_to_dict(child)
                else:
                    value = child.text
                    # Try to convert to appropriate type
                    if value is not None:
                        if value.isdigit():
                            value = int(value)
                        elif value.replace('.', '', 1).isdigit():
                            value = float(value)
                    result[child.tag] = value
    else:
        # Element has no children, just return its text
        value = element.text
        if value is not None:
            if value.isdigit():
                value = int(value)
            elif value.replace('.', '', 1).isdigit():
                value = float(value)
        return value
        
    return result

class TimeCampAPITester:
    def __init__(self, api_token):
        self.api_token = api_token
        self.headers = {"Authorization": f"Bearer {api_token}"}
        self.test_results = []
        
    async def test_endpoint(self, endpoint, method='GET', data=None, description=""):
        """Test a single endpoint"""
        print(f"\n{'='*60}")
        print(f"Testing: {method} {endpoint}")
        if description:
            print(f"Description: {description}")
        print('='*60)
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method=method,
                    url=f"{BASE_URL}/{endpoint}",
                    headers=self.headers,
                    json=data,
                    follow_redirects=False,
                    timeout=10.0
                )
                
                print(f"Status: {response.status_code}")
                
                if response.status_code == 302:
                    print("❌ REDIRECT - Authentication issue!")
                    print(f"Location: {response.headers.get('Location')}")
                    self.test_results.append((endpoint, False, "302 Redirect"))
                    return None
                
                response.raise_for_status()
                
                # Parse response
                if response.text:
                    try:
                        # Try JSON first
                        result = response.json()
                        print("Response type: JSON")
                    except:
                        # Parse XML
                        root = ET.fromstring(response.text)
                        result = xml_to_dict(root)
                        print("Response type: XML")
                    
                    # Show preview based on type
                    if isinstance(result, list):
                        print(f"Result: List with {len(result)} items")
                        if result:
                            print(f"First item: {json.dumps(result[0], indent=2)[:300]}...")
                    elif isinstance(result, dict):
                        print(f"Result: {json.dumps(result, indent=2)[:300]}...")
                    else:
                        print(f"Result: {result}")
                    
                    print("✅ SUCCESS")
                    self.test_results.append((endpoint, True, "OK"))
                    return result
                else:
                    print("Empty response")
                    print("✅ SUCCESS (empty response is valid)")
                    self.test_results.append((endpoint, True, "Empty response"))
                    return {}
                    
            except Exception as e:
                print(f"❌ Error: {str(e)}")
                self.test_results.append((endpoint, False, str(e)))
                return None
    
    async def run_all_tests(self):
        """Run all endpoint tests"""
        print("TimeCamp API Endpoint Tests")
        print(f"Base URL: {BASE_URL}")
        print(f"API Token: {self.api_token[:10]}..." if self.api_token else "NO TOKEN PROVIDED")
        
        # Test 1: Tasks endpoint (includes projects)
        print("\n" + "="*80)
        print("1. TASKS ENDPOINT (Projects and Tasks)")
        print("="*80)
        tasks = await self.test_endpoint(
            'tasks',
            description="Gets all tasks and projects (projects have parent_id=0)"
        )
        
        # Show project count
        if tasks and isinstance(tasks, list):
            projects = [t for t in tasks if t.get('parent_id') == 0]
            print(f"\nFound {len(projects)} projects and {len(tasks)} total tasks")
            if projects:
                print(f"First project: {projects[0].get('name')} (ID: {projects[0].get('task_id')})")
        
        # Test 2: Timer status
        print("\n" + "="*80)
        print("2. TIMER STATUS ENDPOINT")
        print("="*80)
        timer = await self.test_endpoint(
            'timer_running',
            description="Checks if a timer is currently running"
        )
        
        # Test 3: Time entries for today
        print("\n" + "="*80)
        print("3. TIME ENTRIES ENDPOINT (Today)")
        print("="*80)
        today = datetime.now().strftime("%Y-%m-%d")
        entries_today = await self.test_endpoint(
            f'entries?from={today}&to={today}',
            description=f"Gets time entries for today ({today})"
        )
        
        # Test 4: Time entries for this week
        print("\n" + "="*80)
        print("4. TIME ENTRIES ENDPOINT (This Week)")
        print("="*80)
        week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
        week_end = datetime.now().strftime("%Y-%m-%d")
        entries_week = await self.test_endpoint(
            f'entries?from={week_start}&to={week_end}',
            description=f"Gets time entries for this week ({week_start} to {week_end})"
        )
        
        # Test 5: Create a test time entry (optional)
        print("\n" + "="*80)
        print("5. CREATE TIME ENTRY ENDPOINT (Optional Test)")
        print("="*80)
        
        if tasks and len(tasks) > 0:
            # Find a test task or use the first one
            test_task = None
            for task in tasks:
                if 'test' in task.get('name', '').lower():
                    test_task = task
                    break
            
            if not test_task:
                test_task = tasks[0]
            
            print(f"Would create test entry for task: {test_task.get('name')} (ID: {test_task.get('task_id')})")
            print("Skipping actual creation to avoid cluttering your time entries")
            print("To test entry creation, uncomment the code below")
            
            # Uncomment to actually test entry creation:
            # yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            # entry_data = {
            #     "task_id": test_task.get('task_id'),
            #     "date": yesterday,
            #     "start_time": "14:00:00",
            #     "end_time": "15:00:00",
            #     "duration": 3600,
            #     "note": "Test entry from MCP API test script"
            # }
            # await self.test_endpoint('entries', 'POST', entry_data, 
            #                          description="Creates a 1-hour test entry for yesterday")
        
        # Summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print(f"\n{'='*80}")
        print("TEST SUMMARY")
        print('='*80)
        
        passed = sum(1 for _, success, _ in self.test_results if success)
        failed = sum(1 for _, success, _ in self.test_results if not success)
        
        print(f"Total tests: {len(self.test_results)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        
        print("\nDetailed results:")
        for endpoint, success, message in self.test_results:
            status = "✅" if success else "❌"
            print(f"  {status} {endpoint}: {message}")
        
        if failed == 0:
            print("\n🎉 All tests passed! Your TimeCamp MCP server should work correctly.")
        else:
            print("\n⚠️  Some tests failed. Please check your API token and the errors above.")

async def main():
    """Run the test suite"""
    # Get API token from command line or environment
    api_token = None
    
    if len(sys.argv) > 1:
        api_token = sys.argv[1]
    else:
        api_token = os.getenv('TIMECAMP_API_TOKEN')
    
    if not api_token:
        print("ERROR: No API token provided!")
        print("\nUsage:")
        print("  uv run test_timecamp_api.py YOUR_API_TOKEN")
        print("\nOr set environment variable:")
        print("  export TIMECAMP_API_TOKEN=your_token")
        print("  uv run test_timecamp_api.py")
        sys.exit(1)
    
    # Run tests
    tester = TimeCampAPITester(api_token)
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())